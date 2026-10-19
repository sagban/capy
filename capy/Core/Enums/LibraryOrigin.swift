import Foundation

enum LibraryOrigin: String, Codable, CaseIterable {
    case user
    case aiGenerated

    var title: String {
        switch self {
        case .user: "Yours"
        case .aiGenerated: "AI-generated"
        }
    }
}
