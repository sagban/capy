import SwiftUI

struct CapyLiveVoiceSheet: View {
    @Bindable var client: LiveVoiceClient
    var onEnd: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            LiveMeshBackground(mood: mood, reduceMotion: reduceMotion)

            VStack(spacing: 0) {
                liveHeader
                    .padding(.top, 8)

                Spacer(minLength: 12)

                liveOrb

                Text(statusText)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(statusColor)
                    .multilineTextAlignment(.center)
                    .padding(.top, 22)
                    .padding(.horizontal, 28)

                if mood == .listening || mood == .speaking {
                    LiveLevelBars(mood: mood, reduceMotion: reduceMotion)
                        .padding(.top, 18)
                        .accessibilityHidden(true)
                }

                Spacer(minLength: 12)

                captionPanel
                    .padding(.horizontal, 24)

                controlsBar
                    .padding(.top, 28)
                    .padding(.bottom, 12)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.capy.background)
    }

    private var mood: LiveMood {
        switch client.state {
        case .idle:
            return .calm
        case .connecting:
            return .connecting
        case .listening:
            return client.isMuted ? .muted : .listening
        case .speaking:
            return .speaking
        case .error:
            return .trouble
        }
    }

    private var liveHeader: some View {
        HStack {
            HStack(spacing: 8) {
                Circle()
                    .fill(mood == .trouble ? Color.capy.warning : Color.capy.accent)
                    .frame(width: 8, height: 8)
                    .opacity(mood == .connecting ? 0.45 : 1)
                Text("Live")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.capy.textPrimary)
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Capy Live")
    }

    private var liveOrb: some View {
        ZStack {
            LiveRings(mood: mood, reduceMotion: reduceMotion)
            Image("CapyAvatar")
                .resizable()
                .scaledToFill()
                .frame(width: 128, height: 128)
                .clipShape(Circle())
                .overlay(Circle().stroke(Color.capy.surfaceElevated.opacity(0.9), lineWidth: 3))
                .shadow(color: Color.capy.accent.opacity(mood == .speaking ? 0.45 : 0.2), radius: 24, y: 8)
        }
        .frame(height: 280)
        .accessibilityHidden(true)
    }

    private var statusText: String {
        switch client.state {
        case .idle:
            return "Ready"
        case .connecting:
            return "Connecting"
        case .listening:
            return client.isMuted ? "Muted" : "Listening"
        case .speaking:
            return "Speaking"
        case .error(let message):
            return message
        }
    }

    private var statusColor: Color {
        if case .error = client.state {
            return Color.capy.warning
        }
        return Color.capy.textPrimary
    }

    private var captionPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !client.userTranscript.isEmpty {
                Text(client.userTranscript)
                    .font(.body)
                    .foregroundStyle(Color.capy.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            if !client.assistantTranscript.isEmpty {
                Text(client.assistantTranscript)
                    .font(.body.weight(.medium))
                    .foregroundStyle(Color.capy.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            if client.userTranscript.isEmpty && client.assistantTranscript.isEmpty {
                Text("Say what you ate, or ask what fits your remaining budget.")
                    .font(.body)
                    .foregroundStyle(Color.capy.textSecondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
            }
        }
        .lineLimit(4)
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .center)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.capy.surfaceElevated.opacity(0.45), lineWidth: 1)
        )
    }

    private var controlsBar: some View {
        HStack(spacing: 36) {
            Button {
                client.toggleMute()
            } label: {
                VStack(spacing: 8) {
                    Image(systemName: client.isMuted ? "mic.slash.fill" : "mic.fill")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(client.isMuted ? Color.capy.warning : Color.capy.textPrimary)
                        .frame(width: 64, height: 64)
                        .background(.ultraThinMaterial, in: Circle())
                    Text(client.isMuted ? "Unmute" : "Mute")
                        .font(.caption)
                        .foregroundStyle(Color.capy.textSecondary)
                }
            }
            .buttonStyle(.plain)
            .disabled(!client.isActive)
            .accessibilityLabel(client.isMuted ? "Unmute microphone" : "Mute microphone")

            Button {
                onEnd()
            } label: {
                VStack(spacing: 8) {
                    Image(systemName: "phone.down.fill")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(Color.white)
                        .frame(width: 72, height: 72)
                        .background(Color.capy.budgetCalories, in: Circle())
                    Text("End")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.capy.textPrimary)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("End live session")
        }
    }
}

private enum LiveMood: Equatable {
    case calm
    case connecting
    case listening
    case speaking
    case muted
    case trouble

    var speed: Double {
        switch self {
        case .calm, .muted: 0.35
        case .connecting: 0.55
        case .listening: 0.9
        case .speaking: 1.25
        case .trouble: 0.2
        }
    }
}

private struct LiveMeshBackground: View {
    var mood: LiveMood
    var reduceMotion: Bool

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 1 : 1.0 / 30.0)) { timeline in
            let t = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate * mood.speed
            MeshGradient(width: 3, height: 3, points: points(at: t), colors: colors)
                .ignoresSafeArea()
        }
        .overlay {
            LinearGradient(
                colors: [Color.capy.background.opacity(0.15), Color.capy.background.opacity(0.72)],
                startPoint: .center,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            .allowsHitTesting(false)
        }
    }

    private var colors: [Color] {
        switch mood {
        case .speaking:
            return [
                Color.capy.accentSoft, Color.capy.budgetFat, Color.capy.accent,
                Color.capy.accent, Color.capy.surfaceElevated, Color.capy.budgetCarbs,
                Color.capy.background, Color.capy.accentSoft, Color.capy.background,
            ]
        case .listening:
            return [
                Color.capy.accent, Color.capy.accentSoft, Color.capy.budgetCarbs,
                Color.capy.accentSoft, Color.capy.surface, Color.capy.accent,
                Color.capy.background, Color.capy.accentSoft, Color.capy.background,
            ]
        case .connecting:
            return [
                Color.capy.accentSoft, Color.capy.surface, Color.capy.accentSoft,
                Color.capy.surface, Color.capy.background, Color.capy.surface,
                Color.capy.background, Color.capy.accentSoft, Color.capy.background,
            ]
        case .muted, .calm:
            return [
                Color.capy.surface, Color.capy.accentSoft, Color.capy.surface,
                Color.capy.background, Color.capy.surfaceElevated, Color.capy.background,
                Color.capy.background, Color.capy.surface, Color.capy.background,
            ]
        case .trouble:
            return [
                Color.capy.warning, Color.capy.surface, Color.capy.background,
                Color.capy.surface, Color.capy.background, Color.capy.surface,
                Color.capy.background, Color.capy.warning, Color.capy.background,
            ]
        }
    }

    private func points(at time: Double) -> [SIMD2<Float>] {
        let drift = Float(sin(time))
        let driftY = Float(cos(time * 0.8))
        let wobble = Float(sin(time * 1.3)) * 0.06
        return [
            SIMD2(0, 0), SIMD2(0.5 + drift * 0.04, 0), SIMD2(1, 0),
            SIMD2(0, 0.5 + driftY * 0.05), SIMD2(0.5 + wobble, 0.48 + driftY * 0.08), SIMD2(1, 0.5 - drift * 0.04),
            SIMD2(0, 1), SIMD2(0.5 - drift * 0.05, 1), SIMD2(1, 1),
        ]
    }
}

private struct LiveRings: View {
    var mood: LiveMood
    var reduceMotion: Bool

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 1 : 1.0 / 30.0)) { timeline in
            let phase = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate * mood.speed
            ZStack {
                ForEach(0..<3, id: \.self) { index in
                    let shift = (phase + Double(index) * 0.7).truncatingRemainder(dividingBy: 2.4) / 2.4
                    Circle()
                        .stroke(ringColor.opacity(0.55 * (1 - shift)), lineWidth: 2)
                        .frame(width: 150, height: 150)
                        .scaleEffect(1 + shift * (mood == .speaking ? 1.15 : 0.75))
                }
            }
        }
    }

    private var ringColor: Color {
        switch mood {
        case .speaking: Color.capy.budgetFat
        case .trouble: Color.capy.warning
        case .muted, .calm: Color.capy.textSecondary
        default: Color.capy.accent
        }
    }
}

private struct LiveLevelBars: View {
    var mood: LiveMood
    var reduceMotion: Bool

    var body: some View {
        TimelineView(.animation(minimumInterval: reduceMotion ? 1 : 1.0 / 30.0)) { timeline in
            let t = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate * mood.speed
            HStack(alignment: .center, spacing: 5) {
                ForEach(0..<7, id: \.self) { index in
                    let wave = reduceMotion ? 0.45 : abs(sin(t * 3.2 + Double(index) * 0.55))
                    Capsule()
                        .fill(mood == .speaking ? Color.capy.budgetFat : Color.capy.accent)
                        .frame(width: 5, height: 8 + wave * 28)
                }
            }
            .frame(height: 36)
        }
    }
}
