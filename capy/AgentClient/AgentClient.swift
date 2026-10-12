import Foundation
import FirebaseAuth
import FirebaseCore

/// Thin callable client via HTTPS. Full Capy chat wiring is Phase 3.
actor AgentClient {
    static let shared = AgentClient()

    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(session: URLSession = .shared) {
        self.session = session
    }

    func interpretMeal(_ request: InterpretMealRequest) async throws -> InterpretMealResponse {
        guard let user = Auth.auth().currentUser else {
            throw AgentClientError.unauthenticated
        }
        let token = try await user.getIDToken()
        let url = try endpointURL()
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = CallableEnvelope(data: request)
        urlRequest.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: urlRequest)
        guard let http = response as? HTTPURLResponse else {
            throw AgentClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw AgentClientError.httpStatus(http.statusCode)
        }
        if let envelope = try? decoder.decode(CallableResultEnvelope<InterpretMealResponse>.self, from: data) {
            return envelope.result
        }
        // Emulator / some gateways return the payload at the root.
        return try decoder.decode(InterpretMealResponse.self, from: data)
    }

    private func endpointURL() throws -> URL {
        #if DEBUG
        if ProcessInfo.processInfo.environment["CAPY_USE_FUNCTIONS_EMULATOR"] == "1" {
            let project = FirebaseApp.app()?.options.projectID ?? "demo-capy"
            let path = "http://127.0.0.1:5001/\(project)/us-central1/interpret_meal"
            guard let url = URL(string: path) else { throw AgentClientError.invalidResponse }
            return url
        }
        #endif
        let project = FirebaseApp.app()?.options.projectID ?? "capy"
        guard let url = URL(string: "https://us-central1-\(project).cloudfunctions.net/interpret_meal") else {
            throw AgentClientError.invalidResponse
        }
        return url
    }
}

private struct CallableEnvelope<T: Encodable>: Encodable {
    let data: T
}

private struct CallableResultEnvelope<T: Decodable>: Decodable {
    let result: T
}

enum AgentClientError: Error {
    case unauthenticated
    case invalidResponse
    case httpStatus(Int)
}
