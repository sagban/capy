import Foundation

enum ReadableFoodName {
    /// Soften ALL-CAPS menu titles; keep mixed case as-is.
    static func display(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let head: String
        if let range = trimmed.range(of: " — ") {
            head = String(trimmed[..<range.lowerBound])
        } else if let range = trimmed.range(of: " - ") {
            head = String(trimmed[..<range.lowerBound])
        } else {
            head = trimmed
        }
        let letters = head.filter(\.isLetter)
        guard !letters.isEmpty, letters.allSatisfy(\.isUppercase) else { return head }
        return head.localizedLowercase.localizedCapitalized
    }
}
