import Foundation

struct ChatBubble: Identifiable {
    enum Role { case capy, user, error }

    let serverMessageId: String
    let role: Role
    let text: String
    var manualLog: Bool = false
    var freeTextGrams: Bool = false

    var id: String { serverMessageId }

    init(
        serverMessageId: String = UUID().uuidString,
        role: Role,
        text: String,
        manualLog: Bool = false,
        freeTextGrams: Bool = false
    ) {
        self.serverMessageId = serverMessageId
        self.role = role
        self.text = text
        self.manualLog = manualLog
        self.freeTextGrams = freeTextGrams
    }
}
