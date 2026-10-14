import SwiftUI
import SwiftData

struct RootView: View {
    @Environment(AuthManager.self) private var auth
    @Query private var settings: [AppSettings]
    @State private var splashMinimumElapsed = false

    private var showSplash: Bool {
        !splashMinimumElapsed || !auth.hasResolvedInitialState
    }

    private var onboardingCompleted: Bool {
        settings.first?.onboardingCompleted == true
    }

    private var unitPreferences: UnitPreferences {
        settings.first?.unitPreferences ?? .default
    }

    var body: some View {
        Group {
            if showSplash {
                SplashView()
                    .transition(.opacity)
            } else if !auth.isSignedIn {
                AuthView()
            } else if !onboardingCompleted {
                OnboardingView()
            } else {
                MainTabView()
            }
        }
        .environment(\.unitPreferences, unitPreferences)
        .task {
            try? await Task.sleep(for: .milliseconds(900))
            splashMinimumElapsed = true
        }
        .animation(.easeInOut(duration: 0.35), value: showSplash)
        .animation(.easeInOut(duration: 0.2), value: auth.isSignedIn)
        .animation(.easeInOut(duration: 0.2), value: onboardingCompleted)
    }
}
