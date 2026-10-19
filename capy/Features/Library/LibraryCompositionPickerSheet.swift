import SwiftUI
import SwiftData

/// Search catalog (+ library for meals), then push portion screen.
struct LibraryCompositionPickerSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var libraryItems: [LibraryItem]

    let compositionKind: LibraryKind
    var excludeLibraryId: String?
    let onConfirm: (LibraryIngredientLine) -> Void

    @State private var query = ""
    @State private var catalogHits: [Food] = []
    @State private var searchTask: Task<Void, Never>?
    @State private var path = NavigationPath()

    private var libraryHits: [LibraryItem] {
        guard compositionKind == .meal else { return [] }
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let base = libraryItems.filter { item in
            if let excludeLibraryId, item.uuidString == excludeLibraryId { return false }
            return true
        }
        guard !q.isEmpty else { return Array(base.prefix(20)) }
        return base.filter {
            $0.name.lowercased().contains(q) || $0.detail.lowercased().contains(q)
        }.prefix(20).map { $0 }
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    TextField(
                        compositionKind == .meal ? "Search foods, recipes, meals" : "Search foods",
                        text: $query
                    )
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                }

                if compositionKind == .meal, !libraryHits.isEmpty {
                    Section("Library") {
                        ForEach(libraryHits, id: \.uuidString) { item in
                            Button {
                                path.append(CompositionPickDraft.from(libraryItem: item))
                            } label: {
                                FoodPickRow(
                                    title: item.name,
                                    portionGrams: LibraryIngredientLine.from(libraryItem: item).servingGrams,
                                    subtitle: String(item.kind.title.dropLast()),
                                    detail: "\(Int(item.calories.rounded())) cal / serving"
                                )
                            }
                        }
                    }
                }

                if !catalogHits.isEmpty {
                    Section("Catalog") {
                        ForEach(catalogHits, id: \.id) { food in
                            Button {
                                path.append(CompositionPickDraft.from(food: food))
                            } label: {
                                FoodPickRow(
                                    title: food.canonicalName,
                                    portionGrams: catalogServingGrams(food),
                                    subtitle: food.isComposite ? "Composite" : food.ingredientFamily,
                                    detail: catalogSubtitle(food)
                                )
                            }
                        }
                    }
                } else if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                          libraryHits.isEmpty {
                    Section {
                        Text("No matches")
                            .foregroundStyle(.secondary)
                    }
                } else if compositionKind == .recipe,
                          query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    Section {
                        Text("Type to search the catalog.")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle(compositionKind == .meal ? "Add item" : "Add ingredient")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .navigationDestination(for: CompositionPickDraft.self) { draft in
                LibraryCompositionPortionView(draft: draft) { line in
                    onConfirm(line)
                    dismiss()
                }
            }
            .onAppear { refreshCatalog(for: query) }
            .onChange(of: query) { _, newValue in
                searchTask?.cancel()
                searchTask = Task { @MainActor in
                    try? await Task.sleep(for: .milliseconds(200))
                    guard !Task.isCancelled else { return }
                    refreshCatalog(for: newValue)
                }
            }
            .onDisappear { searchTask?.cancel() }
        }
    }

    private func refreshCatalog(for text: String) {
        catalogHits = SeedImporter.searchFoods(query: text, in: modelContext, limit: 30)
    }

    private func catalogServingGrams(_ food: Food) -> Double {
        if food.servingGrams > 0 { return food.servingGrams }
        return PortionDefaults.servingGrams(
            family: food.ingredientFamily,
            name: food.canonicalName,
            kcalPer100g: food.caloriesPer100g
        )
    }

    private func catalogSubtitle(_ food: Food) -> String {
        let serving = catalogServingGrams(food)
        let macros = PortionDefaults.scaledMacros(per100g: food.per100g, grams: serving)
        let cal = "\(Int(macros.calories.rounded())) cal"
        if food.servingLabel.isEmpty { return cal }
        return "\(cal) / \(food.servingLabel)"
    }
}
