import Foundation
import FirebaseAuth
import FirebaseCore

/// Thin callable client. Endpoint selected by `EnvironmentConfig` (Local vs Prod scheme).
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
        let project = FirebaseApp.app()?.options.projectID
            ?? EnvironmentConfig.firebaseProjectID
        guard let url = EnvironmentConfig.interpretMealURL(projectID: project) else {
            throw AgentClientError.invalidResponse
        }
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encoder.encode(CallableEnvelope(data: request))

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
        return try decoder.decode(InterpretMealResponse.self, from: data)
    }
}

private struct CallableEnvelope<T: Encodable>: Encodable {
    let data: T
}

private struct CallableResultEnvelope<T: Decodable>: Decodable {
    let result: T
}

enum AgentClientError: Error, LocalizedError {
    case unauthenticated
    case invalidResponse
    case httpStatus(Int)

    var errorDescription: String? {
        switch self {
        case .unauthenticated: "Sign in required."
        case .invalidResponse: "Unexpected harness response."
        case .httpStatus(let code): "Harness error (\(code))."
        }
    }
}
