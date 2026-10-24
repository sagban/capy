import Foundation
import FirebaseFunctions

/// Build-time environment selected by Xcode scheme → xcconfig (`CAPY_ENVIRONMENT`).
enum AppEnvironment: String, Sendable {
    case local
    case prod

    /// From `app/Config/Secrets.xcconfig` → Info.plist. Same project for the emulator and prod callables.
    var firebaseProjectID: String { Self.plistString("CAPYFirebaseProjectID") }

    var functionsRegion: String { "us-central1" }
    var functionsName: String { "interpret_meal" }

    /// Functions origin for this environment (emulator vs deployed).
    var baseURL: URL {
        switch self {
        case .local:
            URL(string: "http://\(Self.emulatorHost):5001")!
        case .prod:
            URL(string: "https://\(functionsRegion)-\(firebaseProjectID).cloudfunctions.net")!
        }
    }

    /// Streamable HTTP MCP. Trailing slash is required.
    /// Local is `cloudrun.app` on port 8080. Prod is `CAPYHostedMCPURL` from Secrets.xcconfig.
    var hostedMCPURL: URL {
        switch self {
        case .local:
            return URL(string: "http://\(Self.emulatorHost):8080/mcp/")!
        case .prod:
            let raw = Self.plistString("CAPYHostedMCPURL")
            return URL(string: raw) ?? URL(string: "https://missing-mcp-url.invalid/mcp/")!
        }
    }

    /// Cloud Run WebSocket for Gemini Live voice (`/v1/live`).
    var liveVoiceWebSocketURL: URL {
        switch self {
        case .local:
            return URL(string: "ws://\(Self.emulatorHost):8080/v1/live")!
        case .prod:
            var components = URLComponents(url: hostedMCPURL, resolvingAgainstBaseURL: false)
            let scheme = (components?.scheme ?? "https").lowercased()
            components?.scheme = (scheme == "http" || scheme == "ws") ? "ws" : "wss"
            components?.path = "/v1/live"
            components?.query = nil
            return components?.url ?? URL(string: "wss://missing-mcp-url.invalid/v1/live")!
        }
    }

    /// Full callable URL for raw clients (SDK preferred in prod; local uses HTTP).
    var interpretMealURL: URL {
        switch self {
        case .local:
            baseURL
                .appendingPathComponent(firebaseProjectID)
                .appendingPathComponent(functionsRegion)
                .appendingPathComponent(functionsName)
        case .prod:
            baseURL.appendingPathComponent(functionsName)
        }
    }

    /// Firebase Functions client pointed at this environment.
    func makeFunctions() -> Functions {
        let functions = Functions.functions(region: functionsRegion)
        // Local baseURL is the emulator; SDK needs host/port separately from HTTPS prod.
        if self == .local, let host = baseURL.host {
            functions.useEmulator(withHost: host, port: baseURL.port ?? 5001)
        }
        return functions
    }

    /// Host for the Functions emulator.
    /// Simulator always uses loopback. Physical device uses `CAPYEmulatorHost` from
    /// `app/Config/LocalEmulatorHost.xcconfig` (written by `./run.sh` = Mac LAN IP).
    static func plistString(_ key: String) -> String {
        (
            Bundle.main.object(forInfoDictionaryKey: key) as? String
        )?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    static var emulatorHost: String {
        #if targetEnvironment(simulator)
        return "127.0.0.1"
        #else
        let fromPlist = (
            Bundle.main.object(forInfoDictionaryKey: "CAPYEmulatorHost") as? String
        )?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let fromPlist, !fromPlist.isEmpty { return fromPlist }
        return "127.0.0.1"
        #endif
    }
}

enum EnvironmentConfig {
    /// Active environment from scheme (`CAPY_LOCAL`) or Info.plist.
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

    static var firebaseProjectID: String { environment.firebaseProjectID }
    static var functionsName: String { environment.functionsName }
    static var baseURL: URL { environment.baseURL }
    static var interpretMealURL: URL { environment.interpretMealURL }
    static var hostedMCPURL: URL { environment.hostedMCPURL }
    static var liveVoiceWebSocketURL: URL { environment.liveVoiceWebSocketURL }

    static func makeFunctions() -> Functions { environment.makeFunctions() }

    static func callableURL(named functionName: String) -> URL {
        environment.callableURL(named: functionName)
    }
}

extension AppEnvironment {
    func callableURL(named functionName: String) -> URL {
        switch self {
        case .local:
            return baseURL
                .appendingPathComponent(firebaseProjectID)
                .appendingPathComponent(functionsRegion)
                .appendingPathComponent(functionName)
        case .prod:
            return baseURL.appendingPathComponent(functionName)
        }
    }
}
