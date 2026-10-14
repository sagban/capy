import SwiftUI
import SwiftData

struct ManualLogSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var library: [LibraryItem]

    let initialDay: Date
    let initialMealSlot: String?

    @State private var query = ""
    @State private var catalogResults: [Food] = []
    @State private var searchTask: Task<Void, Never>?
    @State private var path = NavigationPath()

    init(dayKey: String, initialMealSlot: String? = nil) {
        self.initialDay = DayKey.date(from: dayKey) ?? Calendar.current.startOfDay(for: .now)
        self.initialMealSlot = initialMealSlot
    }

    init(initialDay: Date, initialMealSlot: String? = nil) {
        self.initialDay = Calendar.current.startOfDay(for: initialDay)
        self.initialMealSlot = initialMealSlot
    }

    private var filteredLibrary: [LibraryItem] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return Array(library.prefix(20)) }
        return library.filter {
            $0.name.lowercased().contains(q) || $0.detail.lowercased().contains(q)
        }
    }

    private var filteredCatalog: [Food] { catalogResults }

    var body: some View {
        NavigationStack(path: $path) {
            foodPicker
                .navigationTitle("Select food")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                    }
                }
                .navigationDestination(for: FoodLogDraft.self) { draft in
                    LogFoodDetailsView(draft: draft, existingEntry: nil) {
                        dismiss()
                    }
                }
                .onAppear {
                    MealTypeCatalog.seedIfNeeded(in: modelContext)
                    refreshCatalog(for: query)
                }
                .onChange(of: query) { _, newValue in
                    searchTask?.cancel()
                    searchTask = Task { @MainActor in
                        try? await Task.sleep(for: .milliseconds(200))
                        guard !Task.isCancelled else { return }
                        refreshCatalog(for: newValue)
                    }
                }
                .onDisappear {
                    searchTask?.cancel()
                }
        }
    }

    private func refreshCatalog(for text: String) {
        catalogResults = SeedImporter.searchFoods(query: text, in: modelContext, limit: 30)
    }

    private var foodPicker: some View {
        List {
            Section {
                TextField("Search meals, recipes, foods", text: $query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }

            if !filteredCatalog.isEmpty {
                Section("Catalog") {
                    ForEach(filteredCatalog, id: \.id) { food in
                        Button {
                            path.append(draft(from: food))
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(food.canonicalName)
                                        .foregroundStyle(Color.primary)
                                    Text(food.isComposite ? "Composite" : food.ingredientFamily)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text("\(Int(food.caloriesPer100g)) cal / 100g · P \(Int(food.proteinGPer100g)) · C \(Int(food.carbsGPer100g)) · F \(Int(food.fatGPer100g))")
                                        .font(.caption2)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
            }

            if !filteredLibrary.isEmpty {
                Section("Library") {
                    ForEach(filteredLibrary) { item in
                        Button {
                            path.append(draft(from: item))
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.name)
                                        .foregroundStyle(Color.primary)
                                    Text(item.detail.isEmpty ? item.origin.title : item.detail)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Text("\(Int(item.calories)) cal · P \(Int(item.proteinG)) · C \(Int(item.carbsG)) · F \(Int(item.fatG))")
                                        .font(.caption2)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
            } else if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                      filteredCatalog.isEmpty {
                Section {
                    Text("No catalog or library matches")
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                Button {
                    path.append(customDraft())
                } label: {
                    Label(
                        query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        ? "Add custom food"
                        : "Use “\(query.trimmingCharacters(in: .whitespacesAndNewlines))”",
                        systemImage: "plus.circle.fill"
                    )
                    .foregroundStyle(Color.capy.accent)
                }
            } footer: {
                Text("Pick a food first. Next you’ll set meal, date, and portion.")
            }
        }
        .scrollDismissesKeyboard(.interactively)
    }

    private func draft(from food: Food) -> FoodLogDraft {
        FoodLogDraft(
            name: food.canonicalName,
            detail: food.isComposite ? "Composite" : food.ingredientFamily,
            baseGrams: 100,
            baseCalories: food.caloriesPer100g,
            baseProteinG: food.proteinGPer100g,
            baseCarbsG: food.carbsGPer100g,
            baseFatG: food.fatGPer100g,
            grams: 100,
            day: initialDay,
            mealSlot: initialMealSlot ?? "",
            allowMacroEdit: false,
            foodId: food.id,
            ingredientFamily: food.ingredientFamily
        )
    }

    private func draft(from item: LibraryItem) -> FoodLogDraft {
        FoodLogDraft(
            name: item.name,
            detail: item.detail.isEmpty ? item.origin.title : item.detail,
            baseGrams: 100,
            baseCalories: item.calories,
            baseProteinG: item.proteinG,
            baseCarbsG: item.carbsG,
            baseFatG: item.fatG,
            grams: 100,
            day: initialDay,
            mealSlot: initialMealSlot ?? "",
            allowMacroEdit: false
        )
    }

    private func customDraft() -> FoodLogDraft {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        return FoodLogDraft(
            name: trimmed,
            detail: "Custom",
            baseGrams: 100,
            baseCalories: 200,
            baseProteinG: 10,
            baseCarbsG: 20,
            baseFatG: 8,
            grams: 100,
            day: initialDay,
            mealSlot: initialMealSlot ?? "",
            allowMacroEdit: true
        )
    }
}

struct FoodLogDraft: Hashable {
    var name: String
    var detail: String
    var baseGrams: Double
    var baseCalories: Double
    var baseProteinG: Double
    var baseCarbsG: Double
    var baseFatG: Double
    var grams: Double
    var day: Date
    var mealSlot: String
    var allowMacroEdit: Bool
    var foodId: String = ""
    var ingredientFamily: String = ""

    private var scale: Double {
        guard baseGrams > 0 else { return 1 }
        return grams / baseGrams
    }

    var calories: Double { baseCalories * scale }
    var proteinG: Double { baseProteinG * scale }
    var carbsG: Double { baseCarbsG * scale }
    var fatG: Double { baseFatG * scale }

    static func from(entry: MealEntry) -> FoodLogDraft {
        let item = entry.items.first
        let grams = max(item?.grams ?? 100, 1)
        return FoodLogDraft(
            name: entry.originalUserText ?? item?.name ?? "Meal",
            detail: item?.name ?? "Logged item",
            baseGrams: grams,
            baseCalories: item?.calories ?? entry.calories,
            baseProteinG: item?.proteinG ?? entry.proteinG,
            baseCarbsG: item?.carbsG ?? entry.carbsG,
            baseFatG: item?.fatG ?? entry.fatG,
            grams: grams,
            day: DayKey.date(from: entry.dayKey) ?? Calendar.current.startOfDay(for: .now),
            mealSlot: entry.mealSlot ?? "",
            allowMacroEdit: true,
            foodId: item?.foodId ?? "",
            ingredientFamily: item?.ingredientFamily ?? ""
        )
    }
}

struct EditMealEntrySheet: View {
    @Environment(\.dismiss) private var dismiss
    let entry: MealEntry

    var body: some View {
        NavigationStack {
            LogFoodDetailsView(
                draft: FoodLogDraft.from(entry: entry),
                existingEntry: entry
            ) {
                dismiss()
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct LogFoodDetailsView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.unitPreferences) private var units
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    @State var draft: FoodLogDraft
    var existingEntry: MealEntry?
    let onSaved: () -> Void

    @State private var didApplyMealSlot = false
    @State private var portionUnit: PortionUnit = .gram

    private var enabledMealTypes: [MealType] {
        mealTypes.filter(\.isEnabled)
    }

    private var portionBinding: Binding<Double> {
        Binding(
            get: {
                portionUnit.amount(fromGrams: draft.grams, servingGrams: draft.baseGrams)
            },
            set: {
                draft.grams = portionUnit.grams(fromAmount: $0, servingGrams: draft.baseGrams)
            }
        )
    }

    var body: some View {
        Form {
            Section {
                TextField("Food name", text: $draft.name)
                    .font(.title3.weight(.bold))
                    .foregroundStyle(Color.capy.textPrimary)
                    .textInputAutocapitalization(.words)
                if !draft.detail.isEmpty, draft.detail != draft.name {
                    Text(draft.detail)
                        .font(.subheadline)
                        .foregroundStyle(Color.capy.textSecondary)
                }
                HStack(spacing: 12) {
                    macroBadge("flame.fill", units.formattedEnergy(draft.calories), Color.capy.budgetCalories)
                    macroBadge("circle.fill", "C \(Int(draft.carbsG.rounded()))", Color.capy.budgetCarbs)
                    macroBadge("circle.fill", "F \(Int(draft.fatG.rounded()))", Color.capy.budgetFat)
                    macroBadge("circle.fill", "P \(Int(draft.proteinG.rounded()))", Color.capy.budgetProtein)
                }
                .padding(.vertical, 2)
            } footer: {
                Text(draft.allowMacroEdit
                     ? "Name this food however you like. Macros below are for the portion you set."
                     : "You can rename what shows in the log.")
            }

            Section {
                DatePicker("Date", selection: $draft.day, displayedComponents: .date)
                if enabledMealTypes.isEmpty {
                    Text("Enable a meal type in Settings first.")
                        .foregroundStyle(.secondary)
                } else {
                    Picker("Meal", selection: $draft.mealSlot) {
                        ForEach(enabledMealTypes) { type in
                            Text(type.name).tag(type.name)
                        }
                    }
                }
            }

            Section {
                HStack(spacing: 10) {
                    Text("Portion")
                    Spacer(minLength: 8)
                    TextField(
                        "0",
                        value: portionBinding,
                        format: .number.precision(.fractionLength(portionUnit.fractionDigits))
                    )
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 72)
                    Picker("Unit", selection: $portionUnit) {
                        ForEach(PortionUnit.allCases) { unit in
                            Text(unit.shortLabel).tag(unit)
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.menu)
                }
            } footer: {
                if portionUnit == .serving {
                    Text("1 serving = \(formatPortionGrams(draft.baseGrams)).")
                }
            }

            Section("Calories & macros") {
                if draft.allowMacroEdit {
                    editableMacroRow(units.energy.title, value: Binding(
                        get: { units.energy(fromKcal: draft.baseCalories) },
                        set: { draft.baseCalories = units.kcal(fromDisplay: $0) }
                    ), suffix: units.energy.shortLabel)
                    editableMacroRow("Protein", value: $draft.baseProteinG, suffix: "g")
                    editableMacroRow("Carbs", value: $draft.baseCarbsG, suffix: "g")
                    editableMacroRow("Fat", value: $draft.baseFatG, suffix: "g")
                    Text("Values are for \(formatPortionGrams(draft.baseGrams)). Portion scales them.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                } else {
                    LabeledContent(units.energy.title, value: units.formattedEnergy(draft.calories))
                    LabeledContent("Protein", value: "\(formatG(draft.proteinG)) g")
                    LabeledContent("Carbs", value: "\(formatG(draft.carbsG)) g")
                    LabeledContent("Fat", value: "\(formatG(draft.fatG)) g")
                }
            }
        }
        .navigationTitle(existingEntry == nil ? "Log food" : "Edit food")
        .navigationBarTitleDisplayMode(.inline)
        .scrollDismissesKeyboard(.interactively)
        .keyboardDoneToolbar()
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button {
                    Keyboard.dismiss()
                    save()
                } label: {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(Color.capy.accent)
                }
                .disabled(!canSave)
                .accessibilityLabel(existingEntry == nil ? "Log food" : "Save changes")
            }
        }
        .onAppear {
            portionUnit = units.foodMass.defaultPortionUnit
            MealTypeCatalog.seedIfNeeded(in: modelContext)
            applyMealSlotIfNeeded()
        }
        .onChange(of: mealTypes.count) { _, _ in
            applyMealSlotIfNeeded()
        }
    }

    private func formatPortionGrams(_ grams: Double) -> String {
        units.formattedFoodMass(grams, decimals: units.foodMass == .ounce ? 1 : 0)
    }

    private var canSave: Bool {
        !draft.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !draft.mealSlot.isEmpty
            && draft.grams > 0
    }

    private func applyMealSlotIfNeeded() {
        guard !didApplyMealSlot || draft.mealSlot.isEmpty else { return }
        if !draft.mealSlot.isEmpty,
           enabledMealTypes.contains(where: { $0.name == draft.mealSlot }) {
            didApplyMealSlot = true
            return
        }
        draft.mealSlot = MealTypeCatalog.suggestedName(from: enabledMealTypes)
            ?? enabledMealTypes.first?.name
            ?? draft.mealSlot
        if !draft.mealSlot.isEmpty {
            didApplyMealSlot = true
        }
    }

    private func save() {
        let item = MealEntryItem(
            name: draft.name,
            grams: draft.grams,
            calories: draft.calories,
            proteinG: draft.proteinG,
            carbsG: draft.carbsG,
            fatG: draft.fatG,
            foodId: draft.foodId,
            ingredientFamily: draft.ingredientFamily
        )

        if let existingEntry {
            for old in existingEntry.items {
                modelContext.delete(old)
            }
            existingEntry.dayKey = DayKey.make(from: draft.day)
            existingEntry.mealSlot = draft.mealSlot
            existingEntry.originalUserText = draft.name
            existingEntry.confirmed = true
            existingEntry.items = [item]
        } else {
            modelContext.insert(
                MealEntry(
                    dayKey: DayKey.make(from: draft.day),
                    mealSlot: draft.mealSlot,
                    originalUserText: draft.name,
                    confirmed: true,
                    items: [item]
                )
            )
        }
        onSaved()
    }

    private func macroBadge(_ systemName: String, _ text: String, _ color: Color) -> some View {
        HStack(spacing: 3) {
            Image(systemName: systemName)
                .font(.caption2)
                .foregroundStyle(color)
            Text(text)
                .font(.caption.weight(.medium))
                .foregroundStyle(Color.capy.textSecondary)
        }
    }

    private func editableMacroRow(_ title: String, value: Binding<Double>, suffix: String) -> some View {
        LabeledContent(title) {
            HStack(spacing: 4) {
                TextField(suffix, value: value, format: .number)
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                Text(suffix)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func formatG(_ value: Double) -> String {
        String(format: "%g", (value * 10).rounded() / 10)
    }
}
