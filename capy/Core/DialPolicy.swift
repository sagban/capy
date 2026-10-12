import Foundation

/// Pure assistance dial policy. No adaptive step-up/down in V1.
enum DialPolicy {
    /// Whether Capy may send unprompted messages (check-ins, nudges).
    static func allowsUnpromptedMessages(_ level: AssistanceLevel) -> Bool {
        switch level {
        case .quiet: false
        case .guided, .fullAssist: true
        }
    }

    /// Guided: one evening decision moment; Full Assist: may initiate more broadly.
    static func allowsEveningCheckIn(_ level: AssistanceLevel) -> Bool {
        switch level {
        case .quiet: false
        case .guided, .fullAssist: true
        }
    }

    /// Full Assist: benefit callout after every completed log.
    static func showsBenefitAfterLog(_ level: AssistanceLevel) -> Bool {
        level == .fullAssist
    }

    /// Reactive log / suggest always available regardless of dial.
    static func allowsReactiveLogAndSuggest(_ level: AssistanceLevel) -> Bool {
        true
    }

    /// Matrix row for tests / docs.
    static func matrix(for level: AssistanceLevel) -> (
        unprompted: Bool,
        eveningCheckIn: Bool,
        benefitAfterLog: Bool,
        reactive: Bool
    ) {
        (
            allowsUnpromptedMessages(level),
            allowsEveningCheckIn(level),
            showsBenefitAfterLog(level),
            allowsReactiveLogAndSuggest(level)
        )
    }
}
