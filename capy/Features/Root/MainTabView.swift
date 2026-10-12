import SwiftUI

struct MainTabView: View {
    @State private var selection = 0

    var body: some View {
        TabView(selection: $selection) {
            Tab("Capy", systemImage: "bubble.left.and.bubble.right", value: 0) {
                CapyTabView()
            }
            Tab("Food Log", systemImage: "list.bullet.clipboard", value: 1) {
                FoodLogTabView()
            }
            Tab("Library", systemImage: "books.vertical", value: 2) {
                LibraryTabView()
            }
        }
        .tint(Color.capy.accent)
    }
}
