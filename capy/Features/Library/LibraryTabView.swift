import SwiftUI
import SwiftData

struct LibraryTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var items: [LibraryItem]

    @State private var kindFilter: LibraryKind = .meal
    @State private var editorKind: LibraryKind = .meal
    @State private var editingItem: LibraryItem?
    @State private var showEditor = false
    @State private var searchText = ""

    private var filteredItems: [LibraryItem] {
        let kindMatched = items.filter { $0.kind == kindFilter }
        let q = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return kindMatched }
        return kindMatched.filter {
            $0.name.lowercased().contains(q) || $0.detail.lowercased().contains(q)
        }
    }

    private var aiItems: [LibraryItem] {
        filteredItems.filter { $0.origin == .aiGenerated }
    }

    private var userItems: [LibraryItem] {
        filteredItems.filter { $0.origin == .user }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                List {
                    Section {
                        Picker("Kind", selection: $kindFilter) {
                            ForEach(LibraryKind.allCases) { kind in
                                Text(kind.title).tag(kind)
                            }
                        }
                        .pickerStyle(.segmented)
                    }

                    Section("AI-generated") {
                        if aiItems.isEmpty {
                            Text(searchText.isEmpty ? "none yet" : "no matches")
                                .foregroundStyle(Color.capy.textSecondary)
                        } else {
                            ForEach(aiItems) { item in
                                Button {
                                    openEditor(item)
                                } label: {
                                    libraryRow(item)
                                }
                            }
                            .onDelete { delete(aiItems, at: $0) }
                        }
                    }

                    Section("Yours") {
                        if userItems.isEmpty {
                            Text(
                                searchText.isEmpty
                                ? "add a custom \(kindFilter.title.lowercased().dropLast())"
                                : "no matches"
                            )
                            .foregroundStyle(Color.capy.textSecondary)
                        } else {
                            ForEach(userItems) { item in
                                Button {
                                    openEditor(item)
                                } label: {
                                    libraryRow(item)
                                }
                            }
                            .onDelete { delete(userItems, at: $0) }
                        }
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Library")
            .searchable(text: $searchText, prompt: "Search library")
            .toolbar {
                SettingsToolbarButton()
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        editingItem = nil
                        editorKind = kindFilter
                        showEditor = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("Add library item")
                }
            }
            .sheet(isPresented: $showEditor, onDismiss: { editingItem = nil }) {
                LibraryEditorSheet(defaultKind: editorKind, existing: editingItem)
                    .presentationDetents(
                        {
                            let kind = editingItem?.kind ?? editorKind
                            return (kind == .recipe || kind == .meal) ? [.large] : [.medium, .large]
                        }()
                    )
            }
        }
    }

    private func openEditor(_ item: LibraryItem) {
        editingItem = item
        editorKind = item.kind
        showEditor = true
    }

    private func libraryRow(_ item: LibraryItem) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(item.name)
                    .font(.headline)
                    .foregroundStyle(Color.capy.textPrimary)
                if item.origin == .aiGenerated {
                    Text("AI")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.capy.accentSoft, in: Capsule())
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
            FoodMacroBadgeRow(
                calories: item.calories,
                carbsG: item.carbsG,
                fatG: item.fatG,
                proteinG: item.proteinG
            )
            if (item.kind == .recipe || item.kind == .meal), !item.ingredients.isEmpty {
                Text(
                    item.kind == .meal
                    ? "\(item.ingredients.count) items"
                    : "\(item.ingredients.count) ingredients"
                )
                .font(.caption)
                .foregroundStyle(Color.capy.textSecondary)
            } else if !item.detail.isEmpty {
                Text(item.detail)
                    .font(.caption)
                    .foregroundStyle(Color.capy.textSecondary)
            }
        }
    }

    private func delete(_ source: [LibraryItem], at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(source[index])
        }
    }
}
