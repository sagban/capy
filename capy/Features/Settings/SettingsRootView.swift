import SwiftUI
import SwiftData

struct SettingsRootView: View {
    var body: some View {
        List {
            Section("General") {
                NavigationLink("User Profile") { UserDetailsView() }
                NavigationLink("Regional & units") { GeneralSettingsView() }
            }
            Section("Nutrition") {
                NavigationLink("Goals") { GoalsSettingsView() }
                NavigationLink("Meal types") { MealTypesSettingsView() }
                NavigationLink("Food preferences") { PreferencesSettingsView(kind: .like) }
                NavigationLink("Diets") { PreferencesSettingsView(kind: .diet) }
            }
            Section("Capy") {
                NavigationLink("Capy Settings") { CapySettingsView() }
                NavigationLink("Memory") { MemorySheetView(embedsNavigation: false) }
                NavigationLink("MCP token") { MCPTokenSettingsView() }
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct GeneralSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var energy: EnergyUnit = .kcal
    @State private var foodMass: FoodMassUnit = .gram
    @State private var bodyMass: BodyMassUnit = .kilogram
    @State private var weekStart: WeekStartPreference = .system

    private var measurementSystem: MeasurementSystem? {
        MeasurementSystem.matching(food: foodMass, body: bodyMass)
    }

    var body: some View {
        Form {
            Section {
                Label {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Regional & units")
                            .font(.title2.weight(.bold))
                        Text("Dates and numbers follow your iPhone region. Choose how Cappy shows energy and weight.")
                            .font(.subheadline)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                } icon: {
                    Image(systemName: "globe")
                        .font(.title2)
                        .foregroundStyle(Color.capy.accent)
                }
            }

            Section("Regional") {
                LabeledContent("Region") {
                    Text(Locale.current.localizedString(forRegionCode: Locale.current.region?.identifier ?? "") ?? "System")
                        .foregroundStyle(Color.capy.textSecondary)
                }
                Picker("Week starts on", selection: $weekStart) {
                    ForEach(WeekStartPreference.allCases) { option in
                        Text(option.title).tag(option)
                    }
                }
                Text("Used by the Food Log calendar. Number and date formats stay with your iPhone language & region.")
                    .font(.footnote)
                    .foregroundStyle(Color.capy.textSecondary)
            }

            Section {
                Picker("Measurement system", selection: Binding(
                    get: { measurementSystem ?? .metric },
                    set: { system in
                        foodMass = system.foodMass
                        bodyMass = system.bodyMass
                    }
                )) {
                    ForEach(MeasurementSystem.allCases) { system in
                        Text(system.title).tag(system)
                    }
                }
                .pickerStyle(.segmented)

                Picker("Energy", selection: $energy) {
                    ForEach(EnergyUnit.allCases) { unit in
                        Text("\(unit.title) (\(unit.shortLabel))").tag(unit)
                    }
                }

                Picker("Food weight", selection: $foodMass) {
                    ForEach(FoodMassUnit.allCases) { unit in
                        Text("\(unit.title) (\(unit.shortLabel))").tag(unit)
                    }
                }

                Picker("Body weight", selection: $bodyMass) {
                    ForEach(BodyMassUnit.allCases) { unit in
                        Text("\(unit.title) (\(unit.shortLabel))").tag(unit)
                    }
                }
            } header: {
                Text("Units")
            } footer: {
                Text("Macros (protein, carbs, fat) stay in grams. Stored values remain kcal and grams; only display changes.")
            }
        }
        .navigationTitle("Regional & units")
        .onAppear(perform: load)
        .onChange(of: energy) { _, _ in save() }
        .onChange(of: foodMass) { _, _ in save() }
        .onChange(of: bodyMass) { _, _ in save() }
        .onChange(of: weekStart) { _, _ in save() }
    }

    private func load() {
        let s = settings.first
        energy = s?.energyUnit ?? .kcal
        foodMass = s?.foodMassUnit ?? .gram
        bodyMass = s?.bodyMassUnit ?? .kilogram
        weekStart = s?.weekStart ?? .system
    }

    private func save() {
        let s = settings.first ?? AppSettings()
        if settings.isEmpty { modelContext.insert(s) }
        s.energyUnit = energy
        s.foodMassUnit = foodMass
        s.bodyMassUnit = bodyMass
        s.weekStart = weekStart
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct GoalsSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]

    @State private var calories = 2000.0
    @State private var protein = 150.0
    @State private var carbs = 200.0
    @State private var fat = 67.0
    @State private var split: MacroSplit = .balanced
    @State private var ready = false

    var body: some View {
        Form {
            Section {
                Label {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Goals")
                            .font(.title2.weight(.bold))
                        Text("Set your calorie and macro targets. Preset splits fill protein, carbs, and fat from calories.")
                            .font(.subheadline)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                } icon: {
                    Image(systemName: "target")
                        .font(.title2)
                        .foregroundStyle(Color.capy.accent)
                }
                .labelStyle(.titleAndIcon)
            }

            Section {
                Stepper(value: $calories, in: 800...6000, step: 50) {
                    HStack {
                        Label("Calories", systemImage: "flame.fill")
                            .foregroundStyle(Color.capy.budgetCalories)
                        Spacer()
                        Text("\(Int(calories)) cal")
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
            }

            Section {
                Picker("Split", selection: $split) {
                    ForEach(MacroSplit.allCases) { option in
                        Text(option.title).tag(option)
                    }
                }
                .pickerStyle(.inline)
                .labelsHidden()

                Text(split.subtitle)
                    .font(.footnote)
                    .foregroundStyle(Color.capy.textSecondary)
            } header: {
                Text("Macros")
            }

            Section {
                if split == .custom {
                    Stepper(value: $protein, in: 20...400, step: 5) {
                        macroRow("Protein", "\(Int(protein)) g", Color.capy.budgetProtein)
                    }
                    Stepper(value: $carbs, in: 20...600, step: 5) {
                        macroRow("Carbs", "\(Int(carbs)) g", Color.capy.budgetCarbs)
                    }
                    Stepper(value: $fat, in: 10...250, step: 5) {
                        macroRow("Fat", "\(Int(fat)) g", Color.capy.budgetFat)
                    }
                } else {
                    LabeledContent("Protein") {
                        Text("\(Int(protein)) g")
                            .foregroundStyle(Color.capy.budgetProtein)
                    }
                    LabeledContent("Carbs") {
                        Text("\(Int(carbs)) g")
                            .foregroundStyle(Color.capy.budgetCarbs)
                    }
                    LabeledContent("Fat") {
                        Text("\(Int(fat)) g")
                            .foregroundStyle(Color.capy.budgetFat)
                    }
                }
            } footer: {
                Text("Changes apply from today forward. Past days keep the goals they already had.")
            }
        }
        .navigationTitle("Goals")
        .onAppear {
            load()
            // Defer so hydrating state doesn't persist as a user edit.
            DispatchQueue.main.async { ready = true }
        }
        .onChange(of: calories) { _, _ in
            guard ready else { return }
            applySplitIfNeeded()
            save()
        }
        .onChange(of: split) { _, _ in
            guard ready else { return }
            applySplitIfNeeded()
            save()
        }
        .onChange(of: protein) { _, _ in
            guard ready, split == .custom else { return }
            save()
        }
        .onChange(of: carbs) { _, _ in
            guard ready, split == .custom else { return }
            save()
        }
        .onChange(of: fat) { _, _ in
            guard ready, split == .custom else { return }
            save()
        }
    }

    private func macroRow(_ title: String, _ value: String, _ color: Color) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value)
                .foregroundStyle(color)
        }
    }

    private func load() {
        if let t = targets.first {
            calories = t.calories
            protein = t.proteinG
            carbs = t.carbsG
            fat = t.fatG
            split = t.macroSplit
        } else {
            applySplitIfNeeded()
        }
    }

    private func applySplitIfNeeded() {
        guard let computed = MacroMath.macros(calories: calories, split: split) else { return }
        protein = computed.proteinG
        carbs = computed.carbsG
        fat = computed.fatG
    }

    private func save() {
        applySplitIfNeeded()
        let start = Calendar.current.startOfDay(for: .now)
        if let existing = targets.first(where: { Calendar.current.isDate($0.effectiveDate, inSameDayAs: start) }) {
            existing.calories = calories
            existing.proteinG = protein
            existing.carbsG = carbs
            existing.fatG = fat
            existing.macroSplit = split
        } else {
            modelContext.insert(
                DailyTarget(
                    effectiveDate: start,
                    calories: calories,
                    proteinG: protein,
                    carbsG: carbs,
                    fatG: fat,
                    macroSplit: split
                )
            )
        }
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct MealTypesSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    @State private var draft = ""

    var body: some View {
        Form {
            Section {
                ForEach(mealTypes) { type in
                    Toggle(isOn: Binding(
                        get: { type.isEnabled },
                        set: {
                            type.isEnabled = $0
                            UserSyncService.shared.scheduleProfileSync(in: modelContext)
                        }
                    )) {
                        HStack {
                            Text(type.name)
                            if type.isSystem {
                                Text("Default")
                                    .font(.caption2.weight(.medium))
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 3)
                                    .background(Color.capy.accentSoft, in: Capsule())
                                    .foregroundStyle(Color.capy.textSecondary)
                            }
                        }
                    }
                }
                .onDelete(perform: deleteCustom)
                .onMove(perform: move)
            } header: {
                Text("Meal types")
            } footer: {
                Text("Enabled types show in Food Log and when logging. Default types can be turned off but not deleted.")
            }

            Section("Add meal type") {
                TextField("e.g. Brunch, Pre-workout", text: $draft)
                Button("Add") { add() }
                    .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .foregroundStyle(Color.capy.accent)
            }
        }
        .navigationTitle("Meal types")
        .toolbar {
            EditButton()
        }
        .onAppear {
            MealTypeCatalog.seedIfNeeded(in: modelContext)
        }
    }

    private func add() {
        let name = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { return }
        if mealTypes.contains(where: { $0.name.caseInsensitiveCompare(name) == .orderedSame }) {
            draft = ""
            return
        }
        let nextOrder = (mealTypes.map(\.sortOrder).max() ?? -1) + 1
        modelContext.insert(MealType(name: name, sortOrder: nextOrder, isEnabled: true, isSystem: false))
        draft = ""
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }

    private func deleteCustom(at offsets: IndexSet) {
        for index in offsets {
            let type = mealTypes[index]
            guard !type.isSystem else { continue }
            modelContext.delete(type)
        }
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }

    private func move(from source: IndexSet, to destination: Int) {
        var ordered = mealTypes
        ordered.move(fromOffsets: source, toOffset: destination)
        for (index, type) in ordered.enumerated() {
            type.sortOrder = index
        }
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct PreferencesSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \UserPreference.createdAt, order: .reverse) private var prefs: [UserPreference]

    let kind: PreferenceKind

    var body: some View {
        Form {
            if kind == .diet {
                PreferenceMultiSelectSection(
                    title: "Diets & patterns",
                    kind: .diet,
                    options: PreferenceCatalog.diets,
                    prefs: prefs,
                    modelContext: modelContext
                )
            } else {
                PreferenceMultiSelectSection(
                    title: "Likes",
                    kind: .like,
                    options: PreferenceCatalog.likes,
                    prefs: prefs,
                    modelContext: modelContext
                )
                PreferenceMultiSelectSection(
                    title: "Dislikes",
                    kind: .dislike,
                    options: PreferenceCatalog.dislikes,
                    prefs: prefs,
                    modelContext: modelContext
                )
                PreferenceMultiSelectSection(
                    title: "Allergies & restrictions",
                    kind: .allergy,
                    options: PreferenceCatalog.allergies,
                    prefs: prefs,
                    modelContext: modelContext
                )
            }
        }
        .navigationTitle(kind == .diet ? "Diets" : "Food preferences")
    }
}

private struct PreferenceMultiSelectSection: View {
    let title: String
    let kind: PreferenceKind
    let options: [String]
    let prefs: [UserPreference]
    let modelContext: ModelContext

    private var selectedValues: Set<String> {
        Set(prefs.filter { $0.kind == kind }.map(\.value))
    }

    var body: some View {
        Section(title) {
            ForEach(options, id: \.self) { option in
                Button {
                    toggle(option)
                } label: {
                    HStack {
                        Text(option)
                            .foregroundStyle(Color.primary)
                        Spacer()
                        if selectedValues.contains(option) {
                            Image(systemName: "checkmark")
                                .fontWeight(.semibold)
                                .foregroundStyle(Color.capy.accent)
                        }
                    }
                }
            }
        }
    }

    private func toggle(_ option: String) {
        if let existing = prefs.first(where: { $0.kind == kind && $0.value == option }) {
            modelContext.delete(existing)
        } else {
            modelContext.insert(UserPreference(kind: kind, value: option))
        }
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct CapySettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var level: AssistanceLevel = .fullAssist
    @State private var responseStyle: ResponseStyle = .balanced
    @State private var hour = 18
    @State private var minute = 0
    @State private var ready = false

    var body: some View {
        Form {
            Section("Assistance dial") {
                Picker("Level", selection: $level) {
                    ForEach(AssistanceLevel.allCases) { Text($0.title).tag($0) }
                }
                Text(level.subtitle)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Section("Reply style") {
                Picker("Style", selection: $responseStyle) {
                    ForEach(ResponseStyle.allCases) { Text($0.title).tag($0) }
                }
                Text(responseStyle.subtitle)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            if level == .guided {
                Section("Evening check-in (in-app)") {
                    Stepper("Hour: \(hour)", value: $hour, in: 12...22)
                    Stepper("Minute: \(minute)", value: $minute, in: 0...59, step: 5)
                }
            }
        }
        .navigationTitle("Capy Settings")
        .onAppear {
            if let s = settings.first {
                level = s.assistanceLevel
                responseStyle = s.responseStyle
                hour = s.guidedCheckInHour
                minute = s.guidedCheckInMinute
            }
            DispatchQueue.main.async { ready = true }
        }
        .onChange(of: level) { _, _ in
            guard ready else { return }
            save()
        }
        .onChange(of: responseStyle) { _, _ in
            guard ready else { return }
            save()
        }
        .onChange(of: hour) { _, _ in
            guard ready else { return }
            save()
        }
        .onChange(of: minute) { _, _ in
            guard ready else { return }
            save()
        }
    }

    private func save() {
        let s = settings.first ?? AppSettings()
        if settings.isEmpty { modelContext.insert(s) }
        s.assistanceLevel = level
        s.responseStyle = responseStyle
        s.guidedCheckInHour = hour
        s.guidedCheckInMinute = minute
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct UserDetailsView: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        Form {
            Section("Account") {
                LabeledContent("Name", value: auth.displayName)
                if let email = auth.email {
                    LabeledContent("Email", value: email)
                }
                LabeledContent("Provider", value: "Google")
            }
            Section {
                Button("Sign out", role: .destructive) {
                    auth.signOut()
                }
            }
            Section {
                Text("Sign in with Apple is deferred for now.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("User details")
    }
}
