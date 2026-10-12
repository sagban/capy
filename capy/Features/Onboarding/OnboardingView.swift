import SwiftUI
import SwiftData

struct OnboardingView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var calories = 2000.0
    @State private var protein = 150.0
    @State private var carbs = 200.0
    @State private var fat = 67.0
    @State private var split: MacroSplit = .balanced
    @State private var dial: AssistanceLevel = .fullAssist
    @State private var selectedDiets: Set<String> = []
    @State private var selectedLikes: Set<String> = []

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                Form {
                    Section("Daily goals") {
                        goalStepper("Calories", value: $calories, step: 50)
                            .onChange(of: calories) { _, _ in applySplitIfNeeded() }

                        Picker("Macro split", selection: $split) {
                            ForEach(MacroSplit.allCases) { option in
                                Text(option.title).tag(option)
                            }
                        }
                        .onChange(of: split) { _, _ in applySplitIfNeeded() }

                        Text(split.subtitle)
                            .font(.footnote)
                            .foregroundStyle(Color.capy.textSecondary)

                        if split == .custom {
                            goalStepper("Protein (g)", value: $protein, step: 5)
                            goalStepper("Carbs (g)", value: $carbs, step: 5)
                            goalStepper("Fat (g)", value: $fat, step: 5)
                        } else {
                            LabeledContent("Protein", value: "\(Int(protein)) g")
                            LabeledContent("Carbs", value: "\(Int(carbs)) g")
                            LabeledContent("Fat", value: "\(Int(fat)) g")
                        }
                    }

                    Section("Capy settings") {
                        Picker("Assistance", selection: $dial) {
                            ForEach(AssistanceLevel.allCases) { level in
                                Text(level.title).tag(level)
                            }
                        }
                        Text(dial.subtitle)
                            .font(.footnote)
                            .foregroundStyle(Color.capy.textSecondary)
                    }

                    Section("Diets (optional)") {
                        ForEach(PreferenceCatalog.diets, id: \.self) { option in
                            selectRow(option, in: $selectedDiets)
                        }
                    }

                    Section("Food preferences (optional)") {
                        ForEach(PreferenceCatalog.likes, id: \.self) { option in
                            selectRow(option, in: $selectedLikes)
                        }
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Quick setup")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Start") { complete() }
                        .fontWeight(.semibold)
                }
            }
            .onAppear { applySplitIfNeeded() }
        }
    }

    private func selectRow(_ option: String, in selection: Binding<Set<String>>) -> some View {
        Button {
            if selection.wrappedValue.contains(option) {
                selection.wrappedValue.remove(option)
            } else {
                selection.wrappedValue.insert(option)
            }
        } label: {
            HStack {
                Text(option)
                    .foregroundStyle(Color.primary)
                Spacer()
                if selection.wrappedValue.contains(option) {
                    Image(systemName: "checkmark")
                        .fontWeight(.semibold)
                        .foregroundStyle(Color.capy.accent)
                }
            }
        }
    }

    private func goalStepper(_ title: String, value: Binding<Double>, step: Double) -> some View {
        Stepper(value: value, in: 0...10_000, step: step) {
            HStack {
                Text(title)
                Spacer()
                Text("\(Int(value.wrappedValue.rounded()))")
                    .foregroundStyle(Color.capy.textSecondary)
            }
        }
    }

    private func applySplitIfNeeded() {
        guard let computed = MacroMath.macros(calories: calories, split: split) else { return }
        protein = computed.proteinG
        carbs = computed.carbsG
        fat = computed.fatG
    }

    private func complete() {
        applySplitIfNeeded()
        let appSettings = settings.first ?? AppSettings()
        if settings.isEmpty {
            modelContext.insert(appSettings)
        }
        appSettings.assistanceLevel = dial
        appSettings.onboardingCompleted = true

        modelContext.insert(
            DailyTarget(
                effectiveDate: Calendar.current.startOfDay(for: .now),
                calories: calories,
                proteinG: protein,
                carbsG: carbs,
                fatG: fat,
                macroSplit: split
            )
        )

        for diet in selectedDiets.sorted() {
            modelContext.insert(UserPreference(kind: .diet, value: diet))
        }
        for like in selectedLikes.sorted() {
            modelContext.insert(UserPreference(kind: .like, value: like))
        }
    }
}
