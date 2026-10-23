import SwiftUI
import SwiftData

struct ManualLogSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var library: [LibraryItem]
    @Query(sort: \MealEntry.timestamp, order: .reverse) private var mealEntries: [MealEntry]

    let initialDay: Date
    let initialMealSlot: String?

    @State private var query = ""
    @State private var catalogResults: [Food] = []
    @State private var searchTask: Task<Void, Never>?
    @State private var path = NavigationPath()
    @State private var showBarcodeScanner = false
    @State private var pendingBarcodeHit: BarcodeLookupHit?
    @State private var pendingMissCustom = false
    @State private var pendingMissSearch = false
    @FocusState private var searchFocused: Bool

    init(dayKey: String, initialMealSlot: String? = nil) {
        self.initialDay = DayKey.date(from: dayKey) ?? Calendar.current.startOfDay(for: .now)
        self.initialMealSlot = initialMealSlot
    }

    init(initialDay: Date, initialMealSlot: String? = nil) {
        self.initialDay = Calendar.current.startOfDay(for: initialDay)
        self.initialMealSlot = initialMealSlot
    }

    private var trimmedQuery: String {
        query.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var isSearching: Bool { !trimmedQuery.isEmpty }

    private var filteredLibrary: [LibraryItem] {
        guard isSearching else { return [] }
        let q = trimmedQuery.lowercased()
        return library.filter {
            $0.name.lowercased().contains(q) || $0.detail.lowercased().contains(q)
        }
    }

    private var filteredCatalog: [Food] { catalogResults }

    /// Distinct recently logged foods (newest first).
    private var recentlyUsed: [FoodLogSuggestion] {
        suggestions(from: mealEntries, mealSlot: nil, limit: 15)
    }

    /// Prior logs for the meal slot this sheet was opened from.
    private var mealSlotSuggestions: [FoodLogSuggestion] {
        guard let slot = initialMealSlot, !slot.isEmpty else { return [] }
        return suggestions(from: mealEntries, mealSlot: slot, limit: 12)
    }

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
                .fullScreenCover(isPresented: $showBarcodeScanner, onDismiss: {
                    if let hit = pendingBarcodeHit {
                        pendingBarcodeHit = nil
                        let next = draft(from: hit)
                        let libraryItem = LibraryItem.upsertFromBarcodeHit(
                            hit,
                            perServing: MacroTotals(
                                calories: next.baseCalories,
                                proteinG: next.baseProteinG,
                                carbsG: next.baseCarbsG,
                                fatG: next.baseFatG
                            ),
                            in: modelContext
                        )
                        try? modelContext.save()
                        UserSyncService.shared.enqueueUpsertLibrary(libraryItem)
                        path.append(next)
                    } else if pendingMissCustom {
                        pendingMissCustom = false
                        path.append(customDraft())
                    } else if pendingMissSearch {
                        pendingMissSearch = false
                        searchFocused = true
                    }
                }) {
                    BarcodeScannerSheet(
                        onHit: { hit in
                            pendingBarcodeHit = hit
                        },
                        onMissSearch: {
                            pendingMissSearch = true
                        },
                        onMissCustom: {
                            pendingMissCustom = true
                        }
                    )
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
                TextField("Search foods", text: $query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($searchFocused)
            }

            if !isSearching {
                if !mealSlotSuggestions.isEmpty {
                    Section("For \(initialMealSlot ?? "this meal")") {
                        ForEach(mealSlotSuggestions) { tip in
                            suggestionRow(tip)
                        }
                    }
                }
                if !recentlyUsed.isEmpty {
                    Section("Recently used") {
                        ForEach(recentlyUsed) { tip in
                            suggestionRow(tip)
                        }
                    }
                } else if mealSlotSuggestions.isEmpty {
                    Section {
                        Text("Type to search the catalog, or add a custom food.")
                            .foregroundStyle(.secondary)
                    }
                }
            } else {
                if !filteredCatalog.isEmpty {
                    Section("Catalog") {
                        ForEach(filteredCatalog, id: \.id) { food in
                            Button {
                                path.append(draft(from: food))
                            } label: {
                                FoodPickRow(
                                    title: food.canonicalName,
                                    portionGrams: catalogServingGrams(food),
                                    subtitle: food.isComposite ? "Composite" : food.ingredientFamily,
                                    detail: catalogDetail(food)
                                )
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
                                FoodPickRow(
                                    title: item.name,
                                    portionGrams: libraryServingGrams(item),
                                    subtitle: item.detail.isEmpty ? item.origin.title : item.detail,
                                    detail: "\(Int(item.calories)) cal / serving"
                                )
                            }
                        }
                    }
                } else if filteredCatalog.isEmpty {
                    Section {
                        Text("No catalog or library matches")
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Section {
                Button {
                    showBarcodeScanner = true
                } label: {
                    Label("Scan barcode", systemImage: "barcode.viewfinder")
                        .foregroundStyle(Color.capy.accent)
                }
                .accessibilityLabel("Scan barcode")

                Button {
                    path.append(customDraft())
                } label: {
                    Label(
                        trimmedQuery.isEmpty
                        ? "Add custom food"
                        : "Use “\(trimmedQuery)”",
                        systemImage: "plus.circle.fill"
                    )
                    .foregroundStyle(Color.capy.accent)
                }
            } footer: {
                Text(isSearching
                     ? "Pick a food, then set meal, date, and portion."
                     : "Start typing to search, or re-log something recent.")
            }
        }
        .scrollDismissesKeyboard(.interactively)
    }

    @ViewBuilder
    private func suggestionRow(_ tip: FoodLogSuggestion) -> some View {
        Button {
            path.append(draft(from: tip))
        } label: {
            FoodPickRow(
                title: tip.name,
                portionGrams: tip.grams,
                subtitle: tip.detail,
                detail: "\(Int(tip.calories)) cal"
            )
        }
    }

    private func catalogServingGrams(_ food: Food) -> Double {
        if food.servingGrams > 0 { return food.servingGrams }
        return PortionDefaults.servingGrams(
            family: food.ingredientFamily,
            name: food.canonicalName,
            kcalPer100g: food.caloriesPer100g
        )
    }

    private func catalogDetail(_ food: Food) -> String {
        let serving = catalogServingGrams(food)
        let macros = PortionDefaults.scaledMacros(per100g: food.per100g, grams: serving)
        let cal = "\(Int(macros.calories.rounded())) cal"
        if food.servingLabel.isEmpty { return cal }
        return "\(cal) / \(food.servingLabel)"
    }

    private func libraryServingGrams(_ item: LibraryItem) -> Double {
        LibraryIngredientLine.from(libraryItem: item, servings: 1).servingGrams
    }

    private func suggestions(
        from entries: [MealEntry],
        mealSlot: String?,
        limit: Int
    ) -> [FoodLogSuggestion] {
        var seen = Set<String>()
        var out: [FoodLogSuggestion] = []
        for entry in entries where entry.confirmed {
            if let mealSlot, (entry.mealSlot ?? "") != mealSlot { continue }
            for item in entry.items {
                let key = item.foodId.isEmpty ? item.name.lowercased() : item.foodId
                guard seen.insert(key).inserted else { continue }
                out.append(
                    FoodLogSuggestion(
                        id: "\(entry.uuid.uuidString)-\(item.persistentModelID)",
                        name: item.name,
                        detail: entry.mealSlot ?? "",
                        foodId: item.foodId,
                        family: item.ingredientFamily,
                        grams: max(item.grams, 1),
                        calories: item.calories,
                        proteinG: item.proteinG,
                        carbsG: item.carbsG,
                        fatG: item.fatG
                    )
                )
                if out.count >= limit { return out }
            }
        }
        return out
    }

    private func draft(from food: Food) -> FoodLogDraft {
        let servingG: Double = {
            if food.servingGrams > 0 { return food.servingGrams }
            return PortionDefaults.servingGrams(
                family: food.ingredientFamily,
                name: food.canonicalName,
                kcalPer100g: food.caloriesPer100g
            )
        }()
        let macros = PortionDefaults.scaledMacros(per100g: food.per100g, grams: servingG)
        let detail: String = {
            if food.isComposite { return "Composite" }
            if !food.servingLabel.isEmpty { return food.servingLabel }
            return food.ingredientFamily
        }()
        return FoodLogDraft(
            name: food.canonicalName,
            detail: detail,
            baseGrams: servingG,
            baseCalories: macros.calories,
            baseProteinG: macros.proteinG,
            baseCarbsG: macros.carbsG,
            baseFatG: macros.fatG,
            grams: servingG,
            day: initialDay,
            mealSlot: initialMealSlot ?? "",
            allowMacroEdit: false,
            foodId: food.id,
            ingredientFamily: food.ingredientFamily
        )
    }

    private func draft(from hit: BarcodeLookupHit) -> FoodLogDraft {
        let servingG: Double = {
            if let g = hit.servingGrams, g > 0 { return g }
            return PortionDefaults.servingGrams(
                family: "",
                name: hit.displayName,
                kcalPer100g: hit.per100g.calories
            )
        }()
        let macros = PortionDefaults.scaledMacros(per100g: hit.per100g, grams: servingG)
        let detail: String = {
            if let brand = hit.brand, !brand.isEmpty { return brand }
            if let label = hit.servingLabel, !label.isEmpty { return label }
            return "Open Food Facts"
        }()
        return FoodLogDraft(
            name: hit.displayName,
            detail: detail,
            baseGrams: servingG,
            baseCalories: macros.calories,
            baseProteinG: macros.proteinG,
            baseCarbsG: macros.carbsG,
            baseFatG: macros.fatG,
            grams: servingG,
            day: initialDay,
            mealSlot: initialMealSlot ?? "",
            allowMacroEdit: false,
            foodId: hit.foodId,
            ingredientFamily: ""
        )
    }

    private func draft(from tip: FoodLogSuggestion) -> FoodLogDraft {
        FoodLogDraft(
            name: tip.name,
            detail: tip.detail.isEmpty ? "Recent" : tip.detail,
            baseGrams: tip.grams,
            baseCalories: tip.calories,
            baseProteinG: tip.proteinG,
            baseCarbsG: tip.carbsG,
            baseFatG: tip.fatG,
            grams: tip.grams,
            day: initialDay,
            mealSlot: initialMealSlot ?? tip.detail,
            allowMacroEdit: false,
            foodId: tip.foodId,
            ingredientFamily: tip.family
        )
    }

    private func draft(from item: LibraryItem) -> FoodLogDraft {
        // Library macros are absolute for one saved portion (= 1 serving).
        return FoodLogDraft(
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
        let trimmed = trimmedQuery
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

private struct FoodLogSuggestion: Identifiable, Hashable {
    let id: String
    let name: String
    let detail: String
    let foodId: String
    let family: String
    let grams: Double
    let calories: Double
    let proteinG: Double
    let carbsG: Double
    let fatG: Double
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
    @State private var portionUnit: PortionUnit = .serving

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
                FoodMacroBadgeRow(
                    calories: draft.calories,
                    carbsG: draft.carbsG,
                    fatG: draft.fatG,
                    proteinG: draft.proteinG
                )
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
                    // Keep the typed number; only the unit’s meaning changes (1 serving → 1 g, not 50 g).
                    .onChange(of: portionUnit) { oldUnit, newUnit in
                        guard oldUnit != newUnit else { return }
                        let amount = oldUnit.amount(
                            fromGrams: draft.grams,
                            servingGrams: draft.baseGrams
                        )
                        draft.grams = newUnit.grams(
                            fromAmount: amount,
                            servingGrams: draft.baseGrams
                        )
                    }
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
        let line = MealCommitLine(
            name: draft.name,
            foodId: draft.foodId,
            grams: draft.grams,
            calories: draft.calories,
            proteinG: draft.proteinG,
            carbsG: draft.carbsG,
            fatG: draft.fatG,
            family: draft.ingredientFamily,
            source: draft.foodId.hasPrefix("off_") ? "web" : ""
        )
        _ = MealCommit.saveManualEntry(
            line: line,
            dayKey: DayKey.make(from: draft.day),
            mealSlot: draft.mealSlot,
            existing: existingEntry,
            barcodePerServing: draft.foodId.hasPrefix("off_")
                ? MacroTotals(
                    calories: draft.baseCalories,
                    proteinG: draft.baseProteinG,
                    carbsG: draft.baseCarbsG,
                    fatG: draft.baseFatG
                )
                : nil,
            barcodeDetail: draft.detail,
            in: modelContext
        )
        onSaved()
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
