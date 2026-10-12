import Foundation

/// Build-time environment selected by Xcode scheme → xcconfig.
enum AppEnvironment: String, Sendable {
    case local
    case prod
}

enum EnvironmentConfig {
    /// Active environment from Info.plist (set by Local.xcconfig / Prod.xcconfig).
    static var environment: AppEnvironment {
        #if CAPY_LOCAL
        return .local
        #else
        let raw = (
            Bundle.main.object(forInfoDictionaryKey: "CAPYEnvironment") as? String
        )?.lowercased()
        return AppEnvironment(rawValue: raw ?? "prod") ?? .prod
        #endif
    }

    static var isLocal: Bool { environment == .local }
    static var isProd: Bool { environment == .prod }

    static var firebaseProjectID: String {
        Bundle.main.object(forInfoDictionaryKey: "FIREBASE_PROJECT_ID") as? String
            ?? "capy-dogfood"
    }

    /// When true, AgentClient targets the Functions emulator.
    static var useFunctionsEmulator: Bool {
        #if CAPY_LOCAL
        return true
        #else
        if let flag = Bundle.main.object(forInfoDictionaryKey: "CAPYUseFunctionsEmulator") as? Bool {
            return flag
        }
        if let raw = Bundle.main.object(forInfoDictionaryKey: "CAPYUseFunctionsEmulator") as? String {
            return ["1", "yes", "true", "YES"].contains(raw)
        }
        return false
        #endif
    }

    static var functionsRegion: String { "us-central1" }
    static var functionsName: String { "interpret_meal" }

    static var functionsEmulatorHost: String { "127.0.0.1" }
    static var functionsEmulatorPort: Int { 5001 }

    /// Callable HTTPS URL for `interpret_meal`.
    static func interpretMealURL(projectID: String) -> URL? {
        if useFunctionsEmulator {
            return URL(
                string: "http://\(functionsEmulatorHost):\(functionsEmulatorPort)/\(projectID)/\(functionsRegion)/\(functionsName)"
            )
        }
        return URL(
            string: "https://\(functionsRegion)-\(projectID).cloudfunctions.net/\(functionsName)"
        )
    }
}
