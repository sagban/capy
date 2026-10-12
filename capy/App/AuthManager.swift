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

    func signOut() {
        errorMessage = nil
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
