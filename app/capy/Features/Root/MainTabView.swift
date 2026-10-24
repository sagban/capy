import SwiftUI
import SwiftData

struct MainTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.scenePhase) private var scenePhase
    @State private var selection = 0

    var body: some View {
        TabView(selection: $selection) {
            Tab("Food Log", systemImage: "list.bullet.clipboard", value: 0) {
                FoodLogTabView()
            }
            Tab("Capy", systemImage: "bubble.left.and.bubble.right", value: 1) {
                CapyTabView()
            }
            Tab("Library", systemImage: "books.vertical", value: 2) {
                LibraryTabView()
            }
        }
        .tint(Color.capy.accent)
        .task {
            await UserSyncService.shared.start()
            UserSyncService.shared.scheduleProfileSync(in: modelContext)
            await UserSyncService.shared.pullLibrary(into: modelContext)
            await UserSyncService.shared.pullDiary(into: modelContext)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task {
                    await UserSyncService.shared.flushPending()
                    UserSyncService.shared.scheduleProfileSync(in: modelContext)
                    await UserSyncService.shared.pullLibrary(into: modelContext)
                    await UserSyncService.shared.pullDiary(into: modelContext)
                }
            }
        }
        .onChange(of: selection) { _, tab in
            guard tab == 0 else { return }
            Task { await UserSyncService.shared.pullDiary(into: modelContext) }
        }
    }
}
