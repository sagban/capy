import SwiftUI
import SwiftData
import FirebaseCore

@main
struct capyApp: App {
    @State private var authManager: AuthManager

    private let sharedModelContainer: ModelContainer

    init() {
        FirebaseApp.configure()
        sharedModelContainer = {
            let schema = Schema([
                AppSettings.self,
                DailyTarget.self,
                UserPreference.self,
                MealEntry.self,
                MealEntryItem.self,
                LibraryItem.self,
            ])
            let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
            do {
                return try ModelContainer(for: schema, configurations: [configuration])
            } catch {
                fatalError("Could not create ModelContainer: \(error)")
            }
        }()
        _authManager = State(initialValue: AuthManager())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(authManager)
        }
        .modelContainer(sharedModelContainer)
    }
}
