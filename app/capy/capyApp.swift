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
                LongTermMemoryNote.self,
                ChatMessageRecord.self,
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
                    MealTypeCatalog.seedIfNeeded(in: sharedModelContainer.mainContext)
                    await SeedImporter.importInBackground(container: sharedModelContainer)
                }
        }
        .modelContainer(sharedModelContainer)
    }
}
