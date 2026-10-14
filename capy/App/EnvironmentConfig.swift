import Foundation
import FirebaseFunctions

/// Build-time environment selected by Xcode scheme → xcconfig (`CAPY_ENVIRONMENT`).
enum AppEnvironment: String, Sendable {
    case local
    case prod

    /// Firebase / GCP project for dogfood (same for Local emulator + Prod callables).
    var firebaseProjectID: String { "capy-dogfood" }

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
    /// `Config/LocalEmulatorHost.xcconfig` (written by `./run.sh` = Mac LAN IP).
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

    static func makeFunctions() -> Functions { environment.makeFunctions() }
}
