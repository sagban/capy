import Foundation
import Observation
import FirebaseAuth
import FirebaseCore
import GoogleSignIn
import UIKit

@MainActor
@Observable
final class AuthManager {
    private(set) var user: User?
    private(set) var isBusy = false
    private(set) var errorMessage: String?
    private(set) var noticeMessage: String?
    /// False until Firebase delivers the first auth state (restored session or none).
    private(set) var hasResolvedInitialState = false
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
                self?.hasResolvedInitialState = true
            }
        }
    }

    deinit {
        if let handle {
            Auth.auth().removeStateDidChangeListener(handle)
        }
    }

    func signInWithGoogle() async {
        clearMessages()
        isBusy = true
        defer { isBusy = false }

        do {
            guard let clientID = FirebaseApp.app()?.options.clientID else {
                throw AuthFlowError.missingClientID
            }
            GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: clientID)

            guard let presenter = Self.topViewController() else {
                throw AuthFlowError.missingPresenter
            }

            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: presenter)
            guard let idToken = result.user.idToken?.tokenString else {
                throw AuthFlowError.missingIDToken
            }
            let accessToken = result.user.accessToken.tokenString
            let credential = GoogleAuthProvider.credential(withIDToken: idToken, accessToken: accessToken)
            _ = try await Auth.auth().signIn(with: credential)
        } catch {
            let ns = error as NSError
            if ns.domain == "com.google.GIDSignIn", ns.code == GIDSignInError.canceled.rawValue {
                return
            }
            errorMessage = error.localizedDescription
        }
    }

    func signIn(email: String, password: String) async {
        await runEmailFlow {
            _ = try await Auth.auth().signIn(withEmail: email, password: password)
        }
    }

    func createAccount(email: String, password: String) async {
        await runEmailFlow {
            _ = try await Auth.auth().createUser(withEmail: email, password: password)
        }
    }

    func sendPasswordReset(email: String) async {
        guard email.contains("@") else {
            clearMessages()
            errorMessage = "Type your email above, then tap Forgot password."
            return
        }
        await runEmailFlow {
            try await Auth.auth().sendPasswordReset(withEmail: email)
            // Email enumeration protection: Firebase reports success even when no account exists.
            self.noticeMessage = "If \(email) has a Capy account, a reset link is on its way. Check spam too."
        }
    }

    func clearMessages() {
        errorMessage = nil
        noticeMessage = nil
    }

    private func runEmailFlow(_ body: () async throws -> Void) async {
        clearMessages()
        isBusy = true
        defer { isBusy = false }
        do {
            try await body()
        } catch {
            errorMessage = Self.emailErrorMessage(for: error)
        }
    }

    private static func emailErrorMessage(for error: Error) -> String {
        let ns = error as NSError
        guard ns.domain == AuthErrorDomain, let code = AuthErrorCode(rawValue: ns.code) else {
            return error.localizedDescription
        }
        switch code {
        case .invalidEmail: return "That email address doesn't look right."
        case .wrongPassword, .invalidCredential, .userNotFound: return "Email or password is incorrect."
        case .emailAlreadyInUse: return "An account with that email already exists. Sign in instead."
        case .weakPassword: return "Password needs at least 6 characters."
        case .networkError: return "No connection. Try again."
        case .tooManyRequests: return "Too many attempts. Wait a moment and try again."
        case .operationNotAllowed: return "Email sign-in isn't enabled for this project."
        default: return error.localizedDescription
        }
    }

    func signOut() {
        clearMessages()
        do {
            try Auth.auth().signOut()
            GIDSignIn.sharedInstance.signOut()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private static func topViewController(
        base: UIViewController? = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    ) -> UIViewController? {
        if let nav = base as? UINavigationController {
            return topViewController(base: nav.visibleViewController)
        }
        if let tab = base as? UITabBarController {
            return topViewController(base: tab.selectedViewController)
        }
        if let presented = base?.presentedViewController {
            return topViewController(base: presented)
        }
        return base
    }
}

enum AuthFlowError: LocalizedError {
    case missingClientID
    case missingPresenter
    case missingIDToken

    var errorDescription: String? {
        switch self {
        case .missingClientID: "Missing Google client ID from Firebase config."
        case .missingPresenter: "Could not present Google Sign-In."
        case .missingIDToken: "Google Sign-In did not return an ID token."
        }
    }
}
