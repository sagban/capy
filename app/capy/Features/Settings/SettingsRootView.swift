import SwiftUI
import SwiftData

struct SettingsRootView: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        List {
            Section {
                NavigationLink {
                    UserDetailsView()
                } label: {
                    HStack(spacing: 14) {
                        ProfileAvatar(name: auth.displayName, photoURL: auth.photoURL, size: 56)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(auth.displayName)
                                .font(.headline)
                                .foregroundStyle(Color.capy.textPrimary)
                            if let email = auth.email {
                                Text(email)
                                    .font(.subheadline)
                                    .foregroundStyle(Color.capy.textSecondary)
                            }
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
            Section("General") {
                NavigationLink {
                    ColorThemeSettingsView()
                } label: {
                    Label("Color theme", systemImage: "paintpalette")
                }
                NavigationLink {
                    GeneralSettingsView()
                } label: {
                    Label("Regional & units", systemImage: "globe")
                }
            }
            Section("Nutrition") {
                NavigationLink {
                    GoalsSettingsView()
                } label: {
                    Label("Goals", systemImage: "target")
                }
                NavigationLink {
                    MealTypesSettingsView()
                } label: {
                    Label("Meal types", systemImage: "fork.knife")
                }
                NavigationLink {
                    PreferencesSettingsView()
                } label: {
                    Label("Food preferences", systemImage: "leaf")
                }
            }
            Section("Capy") {
                NavigationLink {
                    CapySettingsView()
                } label: {
                    Label("Capy Settings", systemImage: "bubble.left.and.bubble.right")
                }
                NavigationLink {
                    MemorySheetView(embedsNavigation: false)
                } label: {
                    Label("Memory", systemImage: "brain.head.profile")
                }
                NavigationLink {
                    MCPTokenSettingsView()
                } label: {
                    Label("MCP token", systemImage: "key")
                }
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ColorThemeSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var theme: ColorTheme = .system

    var body: some View {
        Form {
            Section {
                Label {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Color theme")
                            .font(.title2.weight(.bold))
                        Text("Choose light or dark, or follow your iPhone appearance.")
                            .font(.subheadline)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                } icon: {
                    Image(systemName: "paintpalette")
                        .font(.title2)
                        .foregroundStyle(Color.capy.accent)
                }
            }

            Section {
                Picker("Color theme", selection: $theme) {
                    ForEach(ColorTheme.allCases) { option in
                        Label(option.title, systemImage: option.symbol).tag(option)
                    }
                }
                .pickerStyle(.inline)
                .labelsHidden()
            } footer: {
                Text("Light and dark use the Capy palette. System follows Appearance in iPhone Settings.")
            }
        }
        .navigationTitle("Color theme")
        .onAppear(perform: load)
        .onChange(of: theme) { _, _ in save() }
    }

    private func load() {
        theme = settings.first?.colorTheme ?? .system
    }

    private func save() {
        let s = settings.first ?? AppSettings()
        if settings.isEmpty { modelContext.insert(s) }
        s.colorTheme = theme
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
                        Text("Dates and numbers follow your iPhone region. Choose how Capy shows energy and weight.")
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

    @State private var page: PreferenceKind = .diet

    private static let foodPages: [PreferenceKind] = [.diet, .like, .dislike, .allergy]

    private var activeKind: PreferenceKind { page }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                PreferencePageTabs(page: $page, pages: Self.foodPages)
                Text(hint(for: activeKind))
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textSecondary)
                preferencePills
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color.capy.background)
        .navigationTitle("Food preferences")
        .navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder
    private var preferencePills: some View {
        switch activeKind {
        case .diet:
            PreferencePillGrid(kind: .diet, options: Array(PreferenceCatalog.Diet.allCases), prefs: prefs, modelContext: modelContext)
        case .like:
            PreferencePillGrid(kind: .like, options: Array(PreferenceCatalog.Like.allCases), prefs: prefs, modelContext: modelContext)
        case .dislike:
            PreferencePillGrid(kind: .dislike, options: Array(PreferenceCatalog.Dislike.allCases), prefs: prefs, modelContext: modelContext)
        case .allergy:
            PreferencePillGrid(kind: .allergy, options: Array(PreferenceCatalog.Allergy.allCases), prefs: prefs, modelContext: modelContext)
        }
    }

    private func hint(for kind: PreferenceKind) -> String {
        switch kind {
        case .like: "Foods Capy can suggest."
        case .dislike: "Foods to leave out."
        case .allergy: "Kept out of suggestions."
        case .diet: "Patterns you follow."
        }
    }
}

private struct PreferencePageTabs: View {
    @Binding var page: PreferenceKind
    let pages: [PreferenceKind]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(pages) { item in
                    let selected = page == item
                    Button {
                        withAnimation(.snappy(duration: 0.2)) { page = item }
                    } label: {
                        Label(tabTitle(item), systemImage: tabSymbol(item))
                            .font(.subheadline.weight(.semibold))
                            .labelStyle(.titleAndIcon)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .foregroundStyle(selected ? Color.white : Color.capy.textPrimary)
                            .background(selected ? Color.capy.accent : Color.capy.surfaceElevated, in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(selected ? .isSelected : [])
                }
            }
        }
    }

    private func tabTitle(_ kind: PreferenceKind) -> String {
        switch kind {
        case .like: "Likes"
        case .dislike: "Dislikes"
        case .allergy: "Allergies"
        case .diet: "Diets"
        }
    }

    private func tabSymbol(_ kind: PreferenceKind) -> String {
        switch kind {
        case .like: "heart.fill"
        case .dislike: "hand.thumbsdown.fill"
        case .allergy: "allergens"
        case .diet: "fork.knife"
        }
    }
}

private struct PreferencePillGrid<Option: PreferenceChoice>: View {
    let kind: PreferenceKind
    let options: [Option]
    let prefs: [UserPreference]
    let modelContext: ModelContext

    private var selectedValues: Set<String> {
        Set(prefs.filter { $0.kind == kind }.map(\.value))
    }

    var body: some View {
        PreferenceFlow(spacing: 8) {
            ForEach(options) { option in
                let selected = selectedValues.contains(option.title)
                Button {
                    withAnimation(.snappy(duration: 0.15)) { toggle(option.title) }
                } label: {
                    HStack(spacing: 6) {
                        Text(option.emoji)
                            .accessibilityHidden(true)
                        Text(option.title)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(selected ? Color.capy.accent : Color.capy.textPrimary)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(selected ? Color.capy.accentSoft : Color.capy.surfaceElevated, in: Capsule())
                    .overlay {
                        Capsule()
                            .strokeBorder(selected ? Color.capy.accent : Color(.separator), lineWidth: selected ? 1.5 : 0.5)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityLabel(option.title)
                .accessibilityAddTraits(selected ? .isSelected : [])
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

private struct PreferenceFlow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        let rows = rows(for: width, subviews: subviews)
        let height = rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = rows(for: bounds.width, subviews: subviews)
        var y = bounds.minY
        var index = 0
        for row in rows {
            var x = bounds.minX
            for size in row.sizes {
                subviews[index].place(
                    at: CGPoint(x: x, y: y),
                    proposal: ProposedViewSize(width: size.width, height: size.height)
                )
                x += size.width + spacing
                index += 1
            }
            y += row.height + spacing
        }
    }

    private func rows(for width: CGFloat, subviews: Subviews) -> [(height: CGFloat, sizes: [CGSize])] {
        var rows: [(height: CGFloat, sizes: [CGSize])] = []
        var sizes: [CGSize] = []
        var rowWidth: CGFloat = 0
        var rowHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            let next = rowWidth == 0 ? size.width : rowWidth + spacing + size.width
            if rowWidth > 0, next > width {
                rows.append((rowHeight, sizes))
                sizes = [size]
                rowWidth = size.width
                rowHeight = size.height
            } else {
                sizes.append(size)
                rowWidth = next
                rowHeight = max(rowHeight, size.height)
            }
        }
        if !sizes.isEmpty {
            rows.append((rowHeight, sizes))
        }
        return rows
    }
}

struct CapySettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var level: AssistanceLevel = .fullAssist
    @State private var responseStyle: ResponseStyle = .balanced
    @State private var voiceName: CapyVoice = .puck
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
            Section("Voice") {
                Picker("Voice", selection: $voiceName) {
                    ForEach(CapyVoice.allCases) { Text($0.title).tag($0) }
                }
                Text(voiceName.subtitle)
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
                voiceName = s.voiceName
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
        .onChange(of: voiceName) { _, _ in
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
        s.voiceName = voiceName
        s.guidedCheckInHour = hour
        s.guidedCheckInMinute = minute
        UserSyncService.shared.scheduleProfileSync(in: modelContext)
    }
}

struct ProfileAvatar: View {
    let name: String
    let photoURL: URL?
    var size: CGFloat = 56

    var body: some View {
        Group {
            if let photoURL {
                AsyncImage(url: photoURL) { phase in
                    if let image = phase.image {
                        image.resizable().scaledToFill()
                    } else {
                        initials
                    }
                }
            } else {
                initials
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }

    private var initials: some View {
        Text(String(name.prefix(1)).uppercased())
            .font(.system(size: size * 0.38, weight: .semibold))
            .foregroundStyle(Color.capy.accent)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.capy.accentSoft)
    }
}

struct UserDetailsView: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        Form {
            Section {
                VStack(spacing: 10) {
                    ProfileAvatar(name: auth.displayName, photoURL: auth.photoURL, size: 88)
                    Text(auth.displayName)
                        .font(.title2.weight(.bold))
                        .foregroundStyle(Color.capy.textPrimary)
                    if let email = auth.email {
                        Text(email)
                            .font(.subheadline)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            }
            Section("Account") {
                LabeledContent("Name", value: auth.displayName)
                if let email = auth.email {
                    LabeledContent("Email", value: email)
                }
                LabeledContent("Sign-in", value: auth.signInProvider)
            }
            Section {
                Button("Sign out", role: .destructive) {
                    auth.signOut()
                }
            }
        }
        .navigationTitle("Profile")
    }
}
