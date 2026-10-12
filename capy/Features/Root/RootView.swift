import SwiftUI
import SwiftData

struct RootView: View {
    @Environment(AuthManager.self) private var auth
    @Query private var settings: [AppSettings]

    private var onboardingCompleted: Bool {
        settings.first?.onboardingCompleted == true
    }

    var body: some View {
        Group {
            if !auth.isSignedIn {
                AuthView()
            } else if !onboardingCompleted {
                OnboardingView()
            } else {
                MainTabView()
            }
        }
        .animation(.easeInOut(duration: 0.2), value: auth.isSignedIn)
        .animation(.easeInOut(duration: 0.2), value: onboardingCompleted)
    }
}
