import SwiftUI
import SwiftData

struct LibraryEditorSheet: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss

    let defaultKind: LibraryKind
    var existing: LibraryItem?

    @State private var name = ""
    @State private var kind: LibraryKind
    @State private var detail = ""
    @State private var calories = 400.0
    @State private var protein = 30.0
    @State private var carbs = 40.0
    @State private var fat = 15.0
    @State private var ingredients: [LibraryIngredientLine] = []

    @State private var showAddPicker = false
    @State private var editingLine: LibraryIngredientLine?

    init(defaultKind: LibraryKind, existing: LibraryItem? = nil) {
        self.defaultKind = defaultKind
        self.existing = existing
        _kind = State(initialValue: existing?.kind ?? defaultKind)
    }

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var isComposed: Bool {
        kind == .recipe || kind == .meal
    }

    private var compositionTotals: MacroTotals {
        LibraryIngredientLine.totals(ingredients)
    }

    private var canSave: Bool {
        guard !trimmedName.isEmpty else { return false }
        if isComposed {
            return !ingredients.isEmpty
        }
        return true
    }

    private var navigationTitle: String {
        let editing = existing != nil
        switch kind {
        case .recipe: return editing ? "Edit recipe" : "Add recipe"
        case .meal: return editing ? "Edit meal" : "Add meal"
        case .food: return editing ? "Edit food" : "Add food"
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Item") {
                    TextField("Name", text: $name)
                    Picker("Kind", selection: $kind) {
                        ForEach(LibraryKind.allCases) { Text($0.title).tag($0) }
                    }
                    TextField("Notes", text: $detail)
                }

                if isComposed {
                    Section {
                        Button {
                            showAddPicker = true
                        } label: {
                            Label(
                                kind == .meal ? "Add item" : "Add ingredient",
                                systemImage: "plus.circle.fill"
                            )
                            .foregroundStyle(Color.capy.accent)
                        }
                    } footer: {
                        Text(
                            kind == .meal
                            ? "Pick foods or library recipes/meals, set the portion, then add."
                            : "Pick a food, set the portion, then add."
                        )
                    }

                    Section(kind == .meal ? "Items" : "Ingredients") {
                        if ingredients.isEmpty {
                            Text(kind == .meal ? "No items yet." : "No ingredients yet.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(ingredients) { line in
                                Button {
                                    editingLine = line
                                } label: {
                                    ingredientSummary(line)
                                }
                            }
                            .onDelete { ingredients.remove(atOffsets: $0) }
                        }
                    }

                    Section("Per serving (from items)") {
                        FoodMacroBadgeRow(
                            calories: compositionTotals.calories,
                            carbsG: compositionTotals.carbsG,
                            fatG: compositionTotals.fatG,
                            proteinG: compositionTotals.proteinG
                        )
                    }
                } else {
                    Section("Macros (per serving)") {
                        LabeledContent("Calories") {
                            TextField("cal", value: $calories, format: .number)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                        }
                        LabeledContent("Protein") {
                            TextField("g", value: $protein, format: .number)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                        }
                        LabeledContent("Carbs") {
                            TextField("g", value: $carbs, format: .number)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                        }
                        LabeledContent("Fat") {
                            TextField("g", value: $fat, format: .number)
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                        }
                    }
                }
            }
            .navigationTitle(navigationTitle)
            .navigationBarTitleDisplayMode(.inline)
            .scrollDismissesKeyboard(.interactively)
            .keyboardDoneToolbar()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Keyboard.dismiss()
                        save()
                    }
                    .disabled(!canSave)
                    .fontWeight(.semibold)
                }
            }
            .onAppear(perform: loadExisting)
            .sheet(isPresented: $showAddPicker) {
                LibraryCompositionPickerSheet(
                    compositionKind: kind,
                    excludeLibraryId: existing?.uuidString
                ) { line in
                    ingredients.append(line)
                }
            }
            .sheet(item: $editingLine) { line in
                LibraryCompositionPortionSheet(line: line) { updated in
                    if let index = ingredients.firstIndex(where: { $0.id == updated.id }) {
                        ingredients[index] = updated
                    }
                }
            }
        }
    }

    private func ingredientSummary(_ line: LibraryIngredientLine) -> some View {
        let kindLabel: String = {
            guard line.source == .libraryItem, let lk = line.libraryKind else { return "" }
            return String(lk.title.dropLast())
        }()
        return VStack(alignment: .leading, spacing: 6) {
            FoodPickRow(
                title: line.name,
                portionGrams: line.grams,
                subtitle: kindLabel,
                detail: portionSummary(line)
            )
            FoodMacroBadgeRow(
                calories: line.macros.calories,
                carbsG: line.macros.carbsG,
                fatG: line.macros.fatG,
                proteinG: line.macros.proteinG
            )
        }
    }

    private func portionSummary(_ line: LibraryIngredientLine) -> String {
        let servings = line.grams / max(line.servingGrams, 1)
        if abs(servings - servings.rounded()) < 0.05 {
            let n = Int(servings.rounded())
            return n == 1 ? "1 serving" : "\(n) servings"
        }
        return String(format: "%.1f servings", servings)
    }

    private func loadExisting() {
        guard let existing else { return }
        name = existing.name
        kind = existing.kind
        detail = existing.detail
        calories = existing.calories
        protein = existing.proteinG
        carbs = existing.carbsG
        fat = existing.fatG
        ingredients = existing.ingredients
    }

    private func save() {
        let totals: MacroTotals
        let lines: [LibraryIngredientLine]
        if isComposed {
            lines = ingredients.filter { $0.grams > 0 }
            totals = LibraryIngredientLine.totals(lines)
        } else {
            lines = []
            totals = MacroTotals(
                calories: calories,
                proteinG: protein,
                carbsG: carbs,
                fatG: fat
            )
        }

        let saved: LibraryItem
        if let existing {
            existing.name = trimmedName
            existing.kind = kind
            existing.detail = detail
            existing.calories = totals.calories
            existing.proteinG = totals.proteinG
            existing.carbsG = totals.carbsG
            existing.fatG = totals.fatG
            existing.ingredients = lines
            existing.touchUpdatedAt()
            saved = existing
        } else {
            let item = LibraryItem(
                name: trimmedName,
                kind: kind,
                origin: .user,
                detail: detail,
                calories: totals.calories,
                proteinG: totals.proteinG,
                carbsG: totals.carbsG,
                fatG: totals.fatG,
                ingredients: lines
            )
            modelContext.insert(item)
            saved = item
        }
        try? modelContext.save()
        UserSyncService.shared.enqueueUpsertLibrary(saved)
        dismiss()
    }
}
