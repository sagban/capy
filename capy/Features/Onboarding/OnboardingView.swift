import SwiftUI
import SwiftData

struct OnboardingView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var calories = 2000.0
    @State private var protein = 140.0
    @State private var carbs = 200.0
    @State private var fat = 65.0
    @State private var dial: AssistanceLevel = .fullAssist
    @State private var diet = ""
    @State private var preference = ""

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                Form {
                    Section("Daily goals") {
                        goalStepper("Calories", value: $calories, step: 50)
                        goalStepper("Protein (g)", value: $protein, step: 5)
                        goalStepper("Carbs (g)", value: $carbs, step: 5)
                        goalStepper("Fat (g)", value: $fat, step: 5)
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

                    Section("Starter preferences (optional)") {
                        TextField("Diet tag (e.g. vegetarian)", text: $diet)
                        TextField("Food preference", text: $preference)
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

    private func complete() {
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
                fatG: fat
            )
        )

        if !diet.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            modelContext.insert(UserPreference(kind: .diet, value: diet.trimmingCharacters(in: .whitespacesAndNewlines)))
        }
        if !preference.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            modelContext.insert(UserPreference(kind: .like, value: preference.trimmingCharacters(in: .whitespacesAndNewlines)))
        }
    }
}
