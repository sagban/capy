import AVFoundation
import FirebaseAuth
import Foundation

/// Foreground Gemini Live voice client over `WS /v1/live`.
/// Captures 16 kHz mono 16-bit PCM mic frames, plays 24 kHz mono 16-bit PCM from Capy,
/// and surfaces partial/final transcripts plus `InterpretMealResponseDTO` outcomes.
@Observable
@MainActor
final class LiveVoiceClient {
    enum ConnectionState: Equatable {
        case idle
        case connecting
        case listening
        case speaking
        case error(String)
    }

    var state: ConnectionState = .idle
    var userTranscript = ""
    var assistantTranscript = ""
    var isMuted = false

    var onUserTranscript: ((String, Bool) -> Void)?
    var onAssistantTranscript: ((String, Bool) -> Void)?
    var onOutcome: ((InterpretMealResponseDTO) -> Void)?

    private var webSocketTask: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private let audioEngine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private var playbackFormat: AVAudioFormat?
    private var isEngineRunning = false
    private var pendingBuffers = 0
    /// Speaker audio is still in the room. Keep the mic closed so Capy does not answer itself.
    private var uplinkBlockedUntil = Date.distantPast

    private static let inputSampleRate: Double = 16_000
    private static let outputSampleRate: Double = 24_000

    var isActive: Bool {
        switch state {
        case .connecting, .listening, .speaking:
            return true
        case .idle, .error:
            return false
        }
    }

    func start(
        threadId: String = CapyThreadService.defaultThreadId,
        dayKey: String,
        voiceName: String = CapyVoice.puck.rawValue,
        libraryContext: [LibraryItemRefDTO] = []
    ) async {
        stop()
        userTranscript = ""
        assistantTranscript = ""
        isMuted = false
        state = .connecting

        let micAllowed = await requestMicAuth()
        guard micAllowed else {
            state = .error("Allow microphone access in Settings to talk to Capy.")
            return
        }

        guard let user = Auth.auth().currentUser else {
            state = .error("Sign in required.")
            return
        }

        let idToken: String
        do {
            idToken = try await user.getIDToken()
        } catch {
            state = .error("Couldn’t verify sign-in.")
            return
        }

        do {
            try setupAudioEngine()
        } catch {
            state = .error("Couldn’t start audio.")
            return
        }

        var request = URLRequest(url: EnvironmentConfig.liveVoiceWebSocketURL)
        request.setValue("Bearer \(idToken)", forHTTPHeaderField: "Authorization")

        let task = URLSession.shared.webSocketTask(with: request)
        self.webSocketTask = task
        task.resume()

        let startBody = Self.encodeStartMessage(
            threadId: threadId,
            dayKey: dayKey,
            voiceName: voiceName,
            libraryContext: libraryContext
        )
        do {
            try await task.send(.string(startBody))
        } catch {
            stop()
            state = .error("Couldn’t connect to Capy voice.")
            return
        }

        receiveTask = Task { [weak self] in
            await self?.receiveLoop(task: task)
        }
    }

    func stop() {
        receiveTask?.cancel()
        receiveTask = nil

        if let task = webSocketTask {
            let stopText = #"{"type":"stop"}"#
            task.send(.string(stopText)) { _ in }
            task.cancel(with: .normalClosure, reason: nil)
        }
        webSocketTask = nil

        teardownAudioEngine()
        if case .error = state {
            // Keep visible error if already failed
        } else {
            state = .idle
        }
    }

    func toggleMute() {
        isMuted.toggle()
    }

    // MARK: - WebSocket Loop

    private func receiveLoop(task: URLSessionWebSocketTask) async {
        while !Task.isCancelled {
            do {
                let message = try await task.receive()
                switch message {
                case .data(let data):
                    enqueuePlayback(pcm24kMonoInt16: data)
                case .string(let text):
                    handleServerJSON(text)
                @unknown default:
                    break
                }
            } catch {
                if !Task.isCancelled {
                    teardownAudioEngine()
                    state = .error("Voice session ended.")
                }
                break
            }
        }
    }

    private func handleServerJSON(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String
        else { return }

        switch type {
        case "ready":
            if case .connecting = state {
                state = .listening
            }
        case "interrupted":
            clearPlaybackQueue()
            if isActive {
                state = .listening
            }
        case "user_transcript":
            let transcript = (json["text"] as? String) ?? ""
            let isFinal = (json["final"] as? Bool) ?? false
            userTranscript = transcript
            onUserTranscript?(transcript, isFinal)
            if isFinal {
                assistantTranscript = ""
            }
        case "assistant_transcript":
            let transcript = (json["text"] as? String) ?? ""
            let isFinal = (json["final"] as? Bool) ?? false
            assistantTranscript = transcript
            onAssistantTranscript?(transcript, isFinal)
        case "outcome":
            if let dto = try? JSONDecoder().decode(InterpretMealResponseDTO.self, from: data) {
                onOutcome?(dto)
            }
            if pendingBuffers == 0, isActive {
                state = .listening
            }
        case "error":
            let message = (json["message"] as? String) ?? "Voice session unavailable."
            stop()
            state = .error(message)
        default:
            break
        }
    }

    // MARK: - Audio Engine (16 kHz capture, 24 kHz playback)

    private func setupAudioEngine() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(
            .playAndRecord,
            mode: .voiceChat,
            options: [.defaultToSpeaker, .allowBluetooth, .duckOthers]
        )
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        guard let outFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: Self.outputSampleRate,
            channels: 1,
            interleaved: false
        ) else {
            throw NSError(domain: "LiveVoiceClient", code: -1)
        }
        self.playbackFormat = outFormat

        if playerNode.engine == nil {
            audioEngine.attach(playerNode)
        }
        audioEngine.connect(playerNode, to: audioEngine.mainMixerNode, format: outFormat)

        let inputNode = audioEngine.inputNode
        let hwFormat = inputNode.outputFormat(forBus: 0)
        guard let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: Self.inputSampleRate,
            channels: 1,
            interleaved: true
        ),
        let converter = AVAudioConverter(from: hwFormat, to: targetFormat)
        else {
            throw NSError(domain: "LiveVoiceClient", code: -2)
        }

        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 2048, format: hwFormat) { [weak self] buffer, _ in
            guard let self else { return }
            guard let pcmData = Self.convertToPCM16k(buffer: buffer, converter: converter, targetFormat: targetFormat) else {
                return
            }
            Task { @MainActor [weak self] in
                guard let self, self.uplinkOpen else { return }
                self.webSocketTask?.send(.data(pcmData)) { _ in }
            }
        }

        audioEngine.prepare()
        try audioEngine.start()
        playerNode.play()
        isEngineRunning = true
    }

    private func teardownAudioEngine() {
        if isEngineRunning {
            audioEngine.inputNode.removeTap(onBus: 0)
            playerNode.stop()
            audioEngine.stop()
            isEngineRunning = false
        }
        pendingBuffers = 0
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    private func clearPlaybackQueue() {
        guard isEngineRunning else { return }
        playerNode.stop()
        pendingBuffers = 0
        playerNode.play()
    }

    private func enqueuePlayback(pcm24kMonoInt16 data: Data) {
        guard isEngineRunning,
              let format = playbackFormat,
              data.count >= 2
        else { return }

        let sampleCount = data.count / 2
        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: format,
            frameCapacity: AVAudioFrameCount(sampleCount)
        ),
        let channel = buffer.floatChannelData?[0]
        else { return }

        buffer.frameLength = AVAudioFrameCount(sampleCount)
        data.withUnsafeBytes { raw in
            guard let samples = raw.bindMemory(to: Int16.self).baseAddress else { return }
            for i in 0..<sampleCount {
                channel[i] = Float(Int16(littleEndian: samples[i])) / 32768.0
            }
        }

        pendingBuffers += 1
        state = .speaking
        playerNode.scheduleBuffer(buffer) { [weak self] in
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.pendingBuffers = max(0, self.pendingBuffers - 1)
                if self.pendingBuffers == 0, case .speaking = self.state {
                    self.uplinkBlockedUntil = Date().addingTimeInterval(0.6)
                    self.state = .listening
                }
            }
        }
    }

    private var uplinkOpen: Bool {
        guard !isMuted else { return false }
        guard case .listening = state else { return false }
        return Date() >= uplinkBlockedUntil
    }

    nonisolated private static func convertToPCM16k(
        buffer: AVAudioPCMBuffer,
        converter: AVAudioConverter,
        targetFormat: AVAudioFormat
    ) -> Data? {
        let ratio = targetFormat.sampleRate / buffer.format.sampleRate
        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 32
        guard let outputBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: capacity) else {
            return nil
        }

        var consumed = false
        var error: NSError?
        converter.convert(to: outputBuffer, error: &error) { _, outStatus in
            if consumed {
                outStatus.pointee = .noDataNow
                return nil
            }
            consumed = true
            outStatus.pointee = .haveData
            return buffer
        }
        if error != nil || outputBuffer.frameLength == 0 {
            return nil
        }
        guard let channelData = outputBuffer.int16ChannelData else { return nil }
        let byteCount = Int(outputBuffer.frameLength) * MemoryLayout<Int16>.size
        return Data(bytes: channelData[0], count: byteCount)
    }

    private func requestMicAuth() async -> Bool {
        await withCheckedContinuation { cont in
            AVAudioApplication.requestRecordPermission { granted in
                cont.resume(returning: granted)
            }
        }
    }

    private static func encodeStartMessage(
        threadId: String,
        dayKey: String,
        voiceName: String,
        libraryContext: [LibraryItemRefDTO]
    ) -> String {
        var dict: [String: Any] = [
            "type": "start",
            "threadId": threadId,
            "dayKey": dayKey,
            "voiceName": voiceName,
            "timezone": TimeZone.current.identifier,
            "useServerContext": true,
        ]
        if let libData = try? JSONEncoder().encode(libraryContext),
           let libArray = try? JSONSerialization.jsonObject(with: libData) as? [[String: Any]] {
            dict["libraryContext"] = libArray
        }
        guard let data = try? JSONSerialization.data(withJSONObject: dict),
              let string = String(data: data, encoding: .utf8)
        else {
            return #"{"type":"start"}"#
        }
        return string
    }
}
