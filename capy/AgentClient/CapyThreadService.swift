import Foundation

enum CapyThreadService {
    static let defaultThreadId = "default"
    static let defaultPageLimit = 12

    static func fetchThread(
        threadId: String = defaultThreadId,
        limit: Int = defaultPageLimit,
        cursor: String? = nil
    ) async throws -> GetThreadResponseDTO {
        var payload: [String: Any] = [
            "threadId": threadId,
            "limit": limit,
        ]
        if let cursor, !cursor.isEmpty {
            payload["cursor"] = cursor
        }
        let result = try await AgentClient.shared.callCallable("get_thread", payload: payload)
        let data = try JSONSerialization.data(withJSONObject: result)
        return try JSONDecoder().decode(GetThreadResponseDTO.self, from: data)
    }

    static func appendAssistant(
        _ text: String,
        threadId: String = defaultThreadId,
        clearWorkingMemory: Bool = false
    ) async throws -> GetThreadResponseDTO {
        var payload: [String: Any] = [
            "threadId": threadId,
            "assistantText": text,
        ]
        if clearWorkingMemory {
            payload["clearWorkingMemory"] = true
        }
        let result = try await AgentClient.shared.callCallable("patch_thread", payload: payload)
        let data = try JSONSerialization.data(withJSONObject: result)
        return try JSONDecoder().decode(GetThreadResponseDTO.self, from: data)
    }

    static func noteDayRollover(
        previousDayKey: String,
        mealCount: Int,
        threadId: String = defaultThreadId
    ) async throws {
        _ = try await AgentClient.shared.callCallable(
            "patch_thread",
            payload: [
                "threadId": threadId,
                "dayRollover": [
                    "previousDayKey": previousDayKey,
                    "mealCount": mealCount,
                ],
            ]
        )
    }

    static func chatBubbles(from messages: [ThreadMessageDTO]) -> [ChatBubble] {
        let legacyOpener = "what did you have to eat?"
        return messages.compactMap { message in
            let text = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
            let roleKey = message.role.lowercased()
            if roleKey != "user" && text.lowercased() == legacyOpener { return nil }
            let role: ChatBubble.Role = roleKey == "user" ? .user : .capy
            if text.isEmpty && role == .capy { return nil }
            return ChatBubble(serverMessageId: message.messageId, role: role, text: message.text)
        }
    }
}
