import Foundation
import FirebaseAuth
import FirebaseFunctions

/// Callable client for `interpret_meal`.
/// Request/response schemas are `InterpretMealRequestDTO` / `InterpretMealResponseDTO`.
/// Encodes via `JSONEncoder` (plain numbers) — FirebaseDataEncoder wraps Doubles as
/// protobuf Int64Value/DoubleValue dicts that break server Pydantic validation.
actor AgentClient {
    static let shared = AgentClient()

    /// User-visible failure — never leak status codes, env, or stack names.
    static let gracefulFailureMessage =
        "couldn’t get that just now — try again, or log it from Food Log"

    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    func interpretMeal(_ request: InterpretMealRequestDTO) async throws -> InterpretMealResponseDTO {
        guard Auth.auth().currentUser != nil else {
            throw AgentClientError.unauthenticated
        }

        let payloadData = try encoder.encode(request)
        guard let encoded = try JSONSerialization.jsonObject(with: payloadData) as? [String: Any] else {
            throw AgentClientError.unavailable
        }
        let payload = Self.stripNulls(encoded)

        do {
            #if DEBUG
            print("[AgentClient] \(EnvironmentConfig.environment.rawValue) → \(EnvironmentConfig.interpretMealURL.absoluteString)")
            #endif
            // Local: URLSession to the emulator (SDK often fails on device / cleartext quirks).
            if EnvironmentConfig.isLocal {
                return try await callEmulator(payload: payload)
            }
            return try await callProdSDK(payload: payload)
        } catch let error as AgentClientError {
            throw error
        } catch {
            #if DEBUG
            let ns = error as NSError
            print("[AgentClient] call failed: \(error.localizedDescription) domain=\(ns.domain) code=\(ns.code) [\(EnvironmentConfig.environment.rawValue) \(EnvironmentConfig.baseURL.absoluteString)]")
            #endif
            throw AgentClientError.unavailable
        }
    }

    private func callProdSDK(payload: [String: Any]) async throws -> InterpretMealResponseDTO {
        let callable = EnvironmentConfig.makeFunctions()
            .httpsCallable(EnvironmentConfig.functionsName)
        callable.timeoutInterval = 120
        let result = try await callable.call(payload)
        return try decodeResponse(result.data)
    }

    /// Firebase callable wire format against the Functions emulator HTTP endpoint.
    private func callEmulator(payload: [String: Any]) async throws -> InterpretMealResponseDTO {
        let dict = try await postEmulatorCallable(name: EnvironmentConfig.functionsName, payload: payload)
        return try decodeResponse(dict)
    }

    func callCallable(_ name: String, payload: [String: Any]) async throws -> [String: Any] {
        guard Auth.auth().currentUser != nil else {
            throw AgentClientError.unauthenticated
        }
        let body = Self.stripNulls(payload)
        if EnvironmentConfig.isLocal {
            return try await postEmulatorCallable(name: name, payload: body)
        }
        let callable = EnvironmentConfig.makeFunctions().httpsCallable(name)
        callable.timeoutInterval = 60
        let result = try await callable.call(body)
        return try Self.decodeDictionary(result.data)
    }

    /// Short-lived bearer for an MCP client. Same account as the signed-in user.
    func exchangeAccessToken() async throws -> MCPAccessToken {
        guard let user = Auth.auth().currentUser else {
            throw AgentClientError.unauthenticated
        }
        let idToken = try await user.getIDToken()
        let dict = try await callCallable("exchange_access_token", payload: ["firebaseIdToken": idToken])
        guard let accessToken = dict["accessToken"] as? String, !accessToken.isEmpty else {
            throw AgentClientError.unavailable
        }
        let expiresIn = Self.intValue(dict["expiresIn"]) ?? 3600
        return MCPAccessToken(accessToken: accessToken, expiresIn: expiresIn)
    }

    private static func intValue(_ value: Any?) -> Int? {
        switch value {
        case let number as Int:
            return number
        case let number as Double:
            return Int(number)
        case let number as NSNumber:
            return number.intValue
        default:
            return nil
        }
    }

    /// Exact GTIN → Open Food Facts via `lookup_barcode`.
    func lookupBarcode(gtin: String) async throws -> BarcodeLookupResponseDTO {
        let digits = gtin.filter(\.isNumber)
        guard digits.count >= 8 else {
            return BarcodeLookupResponseDTO(found: false)
        }
        let dict = try await callCallable("lookup_barcode", payload: ["gtin": digits])
        let data = try JSONSerialization.data(withJSONObject: dict)
        do {
            return try decoder.decode(BarcodeLookupResponseDTO.self, from: data)
        } catch {
            #if DEBUG
            print("[AgentClient] lookup_barcode decode failed: \(error)")
            #endif
            throw AgentClientError.unavailable
        }
    }

    static func stripNulls(_ dict: [String: Any]) -> [String: Any] {
        var out: [String: Any] = [:]
        for (key, nested) in dict {
            if nested is NSNull { continue }
            out[key] = stripNullValue(nested)
        }
        return out
    }

    private func postEmulatorCallable(name: String, payload: [String: Any]) async throws -> [String: Any] {
        guard let user = Auth.auth().currentUser else {
            throw AgentClientError.unauthenticated
        }
        let token = try await user.getIDToken()
        var request = URLRequest(url: EnvironmentConfig.callableURL(named: name))
        request.httpMethod = "POST"
        // Match prod interpret_meal (120s); cold Gemini + tools often exceeds 60s locally.
        request.timeoutInterval = 120
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["data": payload])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200 ... 299).contains(http.statusCode) else {
            throw AgentClientError.unavailable
        }
        let envelope = try JSONSerialization.jsonObject(with: data)
        guard let dict = envelope as? [String: Any] else {
            throw AgentClientError.unavailable
        }
        if dict["error"] != nil {
            throw AgentClientError.unavailable
        }
        if let result = dict["result"] {
            return try Self.decodeDictionary(result)
        }
        return try Self.decodeDictionary(dict)
    }

    private static func decodeDictionary(_ data: Any) throws -> [String: Any] {
        if let dict = data as? [String: Any] {
            return dict
        }
        let jsonData: Data
        if let raw = data as? Data {
            jsonData = raw
        } else {
            jsonData = try JSONSerialization.data(withJSONObject: data)
        }
        guard let dict = try JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else {
            throw AgentClientError.unavailable
        }
        return dict
    }

    private static func stripNullValue(_ value: Any) -> Any {
        switch value {
        case let dict as [String: Any]:
            return stripNulls(dict)
        case let array as [Any]:
            return array.compactMap { item -> Any? in
                if item is NSNull { return nil }
                return stripNullValue(item)
            }
        default:
            return value
        }
    }

    private func decodeResponse(_ data: Any) throws -> InterpretMealResponseDTO {
        let jsonData: Data
        if let data = data as? Data {
            jsonData = data
        } else {
            jsonData = try JSONSerialization.data(withJSONObject: data)
        }
        do {
            return try decoder.decode(InterpretMealResponseDTO.self, from: jsonData)
        } catch {
            #if DEBUG
            print("[AgentClient] decode failed: \(error)")
            #endif
            throw AgentClientError.unavailable
        }
    }
}

struct MCPAccessToken: Equatable {
    let accessToken: String
    let expiresIn: Int

    var configJSON: String {
        """
        {
          "mcpServers": {
            "cappy": {
              "url": "\(EnvironmentConfig.hostedMCPURL.absoluteString)",
              "headers": {
                "Authorization": "Bearer \(accessToken)"
              }
            }
          }
        }
        """
    }
}

enum AgentClientError: Error, LocalizedError {
    case unauthenticated
    case unavailable

    var errorDescription: String? {
        switch self {
        case .unauthenticated: "Sign in required."
        case .unavailable: AgentClient.gracefulFailureMessage
        }
    }
}
