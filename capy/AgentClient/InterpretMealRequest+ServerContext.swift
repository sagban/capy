import Foundation

extension InterpretMealRequestDTO {
    /// Minimal `interpret_meal` body when the server loads profile, diary, and thread from Firestore.
    static func serverContext(
        utterance: String,
        dayKey: String,
        timezone: String = TimeZone.current.identifier,
        threadId: String = CapyThreadService.defaultThreadId
    ) -> InterpretMealRequestDTO {
        InterpretMealRequestDTO(
            utterance: utterance,
            timezone: timezone,
            dayKey: dayKey,
            threadId: threadId,
            useServerContext: true
        )
    }
}
