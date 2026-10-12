import SwiftUI

struct MainTabView: View {
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
    }
}
