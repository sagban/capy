import SwiftUI
import SwiftData
import FirebaseCore
import GoogleSignIn

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
                MealType.self,
                MealEntry.self,
                MealEntryItem.self,
                LibraryItem.self,
                Food.self,
                MealTemplate.self,
                MealTemplateItem.self,
                SearchCacheEntry.self,
                ConversationThread.self,
                ConversationTurn.self,
                LongTermMemoryNote.self,
            ])
            let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
            do {
                return try ModelContainer(for: schema, configurations: [configuration])
            } catch {
                fatalError("Could not create ModelContainer: \(error)")
            }
        }()
        let context = sharedModelContainer.mainContext
        MealTypeCatalog.seedIfNeeded(in: context)
        try? SeedImporter.importIfNeeded(into: context)
        _ = ConversationMemoryStore.thread(in: context)
        _authManager = State(initialValue: AuthManager())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(authManager)
                .onOpenURL { url in
                    GIDSignIn.sharedInstance.handle(url)
                }
                .task {
                    let context = sharedModelContainer.mainContext
                    MealTypeCatalog.seedIfNeeded(in: context)
                    try? SeedImporter.importIfNeeded(into: context)
                }
        }
        .modelContainer(sharedModelContainer)
    }
}
