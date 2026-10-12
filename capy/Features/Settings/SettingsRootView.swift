import SwiftUI
import SwiftData

struct SettingsRootView: View {
    var body: some View {
        List {
            NavigationLink("Goals") { GoalsSettingsView() }
            NavigationLink("Food preferences") { PreferencesSettingsView(kind: .like) }
            NavigationLink("Diets") { PreferencesSettingsView(kind: .diet) }
            NavigationLink("Capy Settings") { CapySettingsView() }
            NavigationLink("User details") { UserDetailsView() }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct GoalsSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]

    @State private var calories = 2000.0
    @State private var protein = 140.0
    @State private var carbs = 200.0
    @State private var fat = 65.0

    var body: some View {
        Form {
            Section("Effective today (does not rewrite past days)") {
                Stepper(value: $calories, in: 800...6000, step: 50) {
                    Text("Calories: \(Int(calories))")
                }
                Stepper(value: $protein, in: 20...400, step: 5) {
                    Text("Protein: \(Int(protein)) g")
                }
                Stepper(value: $carbs, in: 20...600, step: 5) {
                    Text("Carbs: \(Int(carbs)) g")
                }
                Stepper(value: $fat, in: 10...250, step: 5) {
                    Text("Fat: \(Int(fat)) g")
                }
            }
            Button("Save new target for today") { save() }
        }
        .navigationTitle("Goals")
        .onAppear {
            if let t = targets.first {
                calories = t.calories
                protein = t.proteinG
                carbs = t.carbsG
                fat = t.fatG
            }
        }
    }

    private func save() {
        let start = Calendar.current.startOfDay(for: .now)
        if let existing = targets.first(where: { Calendar.current.isDate($0.effectiveDate, inSameDayAs: start) }) {
            existing.calories = calories
            existing.proteinG = protein
            existing.carbsG = carbs
            existing.fatG = fat
        } else {
            modelContext.insert(
                DailyTarget(
                    effectiveDate: start,
                    calories: calories,
                    proteinG: protein,
                    carbsG: carbs,
                    fatG: fat
                )
            )
        }
    }
}

struct PreferencesSettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \UserPreference.createdAt, order: .reverse) private var prefs: [UserPreference]

    let kind: PreferenceKind
    @State private var draft = ""

    private var filtered: [UserPreference] {
        prefs.filter { $0.kind == kind }
    }

    private var relatedKinds: [PreferenceKind] {
        kind == .like ? [.like, .dislike, .allergy] : [kind]
    }

    private var rows: [UserPreference] {
        prefs.filter { relatedKinds.contains($0.kind) }
    }

    var body: some View {
        Form {
            if kind == .like {
                Section("Add") {
                    Picker("Type", selection: Binding(
                        get: { addKind },
                        set: { addKind = $0 }
                    )) {
                        Text("Preference").tag(PreferenceKind.like)
                        Text("Dislike").tag(PreferenceKind.dislike)
                        Text("Allergy").tag(PreferenceKind.allergy)
                    }
                    TextField("Value", text: $draft)
                    Button("Add") { add() }
                        .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Section("Saved") {
                    ForEach(rows) { pref in
                        LabeledContent(pref.kind.title, value: pref.value)
                    }
                    .onDelete(perform: deleteRows)
                }
            } else {
                Section("Add diet") {
                    TextField("e.g. vegetarian", text: $draft)
                    Button("Add") { add() }
                        .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                Section {
                    ForEach(filtered) { pref in
                        Text(pref.value)
                    }
                    .onDelete(perform: deleteFiltered)
                }
            }
        }
        .navigationTitle(kind == .diet ? "Diets" : "Food preferences")
    }

    @State private var addKind: PreferenceKind = .like

    private func add() {
        let value = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        let k = kind == .diet ? PreferenceKind.diet : addKind
        modelContext.insert(UserPreference(kind: k, value: value))
        draft = ""
    }

    private func deleteRows(at offsets: IndexSet) {
        for index in offsets { modelContext.delete(rows[index]) }
    }

    private func deleteFiltered(at offsets: IndexSet) {
        for index in offsets { modelContext.delete(filtered[index]) }
    }
}

struct CapySettingsView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var level: AssistanceLevel = .fullAssist
    @State private var hour = 18
    @State private var minute = 0

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
            if level == .guided {
                Section("Evening check-in (in-app)") {
                    Stepper("Hour: \(hour)", value: $hour, in: 12...22)
                    Stepper("Minute: \(minute)", value: $minute, in: 0...59, step: 5)
                }
            }
            Button("Save") { save() }
        }
        .navigationTitle("Capy Settings")
        .onAppear {
            if let s = settings.first {
                level = s.assistanceLevel
                hour = s.guidedCheckInHour
                minute = s.guidedCheckInMinute
            }
        }
    }

    private func save() {
        let s = settings.first ?? AppSettings()
        if settings.isEmpty { modelContext.insert(s) }
        s.assistanceLevel = level
        s.guidedCheckInHour = hour
        s.guidedCheckInMinute = minute
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
