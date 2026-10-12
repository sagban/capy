import Foundation
import Observation
import FirebaseAuth
import AuthenticationServices
import UIKit

@MainActor
@Observable
final class AuthManager {
    private(set) var user: User?
    private(set) var isBusy = false
    private(set) var errorMessage: String?
    nonisolated(unsafe) private var handle: AuthStateDidChangeListenerHandle?

    var isSignedIn: Bool { user != nil }
    var displayName: String {
        user?.displayName ?? user?.email ?? "Signed in"
    }
    var email: String? { user?.email }

    init() {
        user = Auth.auth().currentUser
        handle = Auth.auth().addStateDidChangeListener { [weak self] _, user in
            Task { @MainActor in
                self?.user = user
            }
        }
    }

    deinit {
        if let handle {
            Auth.auth().removeStateDidChangeListener(handle)
        }
    }

    func signInWithGoogle() async {
        errorMessage = nil
        isBusy = true
        defer { isBusy = false }

        do {
            let provider = OAuthProvider(providerID: "google.com")
            provider.scopes = ["profile", "email"]
            let credential = try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<AuthCredential, Error>) in
                provider.getCredentialWith(nil) { credential, error in
                    if let error {
                        continuation.resume(throwing: error)
                        return
                    }
                    guard let credential else {
                        continuation.resume(throwing: AuthFlowError.missingCredential)
                        return
                    }
                    continuation.resume(returning: credential)
                }
            }
            _ = try await Auth.auth().signIn(with: credential)
        } catch {
            let ns = error as NSError
            // User cancel
            if ns.domain == ASWebAuthenticationSessionError.errorDomain,
               ns.code == ASWebAuthenticationSessionError.canceledLogin.rawValue {
                return
            }
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        errorMessage = nil
        do {
            try Auth.auth().signOut()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

enum AuthFlowError: LocalizedError {
    case missingCredential

    var errorDescription: String? {
        switch self {
        case .missingCredential: "Google Sign-In did not return a credential."
        }
    }
}
