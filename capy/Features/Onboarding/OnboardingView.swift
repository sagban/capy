import SwiftUI
import SwiftData

private enum OnboardingStep: Int, CaseIterable, Identifiable {
    case welcome
    case calories
    case macros
    case dial
    case diets
    case likes
    case allergies
    case ready

    var id: Int { rawValue }

    var progressIndex: Int { rawValue }
    static var progressCount: Int { allCases.count }
}

struct OnboardingView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var settings: [AppSettings]

    @State private var step: OnboardingStep = .welcome
    @State private var stepDirection: Int = 1

    @State private var calories = 2000.0
    @State private var protein = 150.0
    @State private var carbs = 200.0
    @State private var fat = 67.0
    @State private var split: MacroSplit = .balanced
    @State private var dial: AssistanceLevel = .fullAssist
    @State private var selectedDiets: Set<String> = []
    @State private var selectedLikes: Set<String> = []
    @State private var selectedAllergies: Set<String> = []

    var body: some View {
        ZStack {
            CapyScreenBackground()

            VStack(spacing: 0) {
                progressBar
                    .padding(.horizontal, 24)
                    .padding(.top, 16)
                    .padding(.bottom, 8)

                ZStack {
                    stepContent
                        .id(step)
                        .transition(stepTransition)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                bottomBar
                    .padding(.horizontal, 24)
                    .padding(.bottom, 28)
                    .padding(.top, 12)
            }
        }
        .onAppear { applySplitIfNeeded() }
    }

    // MARK: - Chrome

    private var progressBar: some View {
        GeometryReader { geo in
            let fraction = CGFloat(step.progressIndex + 1) / CGFloat(OnboardingStep.progressCount)
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.capy.surfaceElevated.opacity(0.8))
                Capsule()
                    .fill(Color.capy.accent)
                    .frame(width: max(8, geo.size.width * fraction))
                    .animation(.easeInOut(duration: 0.28), value: step)
            }
        }
        .frame(height: 4)
        .accessibilityLabel("Setup progress")
        .accessibilityValue("Step \(step.progressIndex + 1) of \(OnboardingStep.progressCount)")
    }

    private var stepTransition: AnyTransition {
        .asymmetric(
            insertion: .move(edge: stepDirection >= 0 ? .trailing : .leading).combined(with: .opacity),
            removal: .move(edge: stepDirection >= 0 ? .leading : .trailing).combined(with: .opacity)
        )
    }

    @ViewBuilder
    private var stepContent: some View {
        switch step {
        case .welcome:
            welcomeStep
        case .calories:
            caloriesStep
        case .macros:
            macrosStep
        case .dial:
            dialStep
        case .diets:
            chipStep(
                title: "Any diet you follow?",
                subtitle: "Optional — skip if none fit.",
                options: PreferenceCatalog.diets,
                selection: $selectedDiets
            )
        case .likes:
            chipStep(
                title: "What do you usually go for?",
                subtitle: "Pick a few. You can change these later.",
                options: PreferenceCatalog.likes,
                selection: $selectedLikes
            )
        case .allergies:
            chipStep(
                title: "Anything to avoid for allergies?",
                subtitle: "We’ll keep these out of suggestions.",
                options: PreferenceCatalog.allergies,
                selection: $selectedAllergies
            )
        case .ready:
            readyStep
        }
    }

    private var bottomBar: some View {
        HStack(spacing: 12) {
            if step != .welcome {
                Button("Back") { goBack() }
                    .fontWeight(.semibold)
                    .foregroundStyle(Color.capy.textSecondary)
                    .padding(.vertical, 14)
                    .padding(.horizontal, 8)
            }

            Spacer(minLength: 0)

            Button {
                if step == .ready {
                    complete()
                } else {
                    goForward()
                }
            } label: {
                Text(primaryButtonTitle)
                    .fontWeight(.semibold)
                    .frame(maxWidth: step == .welcome || step == .ready ? .infinity : nil)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color.capy.accent)
        }
    }

    private var primaryButtonTitle: String {
        switch step {
        case .welcome: "Let’s go"
        case .diets, .likes, .allergies:
            selectionEmpty(for: step) ? "Skip" : "Continue"
        case .ready: "Open Food Log"
        default: "Continue"
        }
    }

    private func selectionEmpty(for step: OnboardingStep) -> Bool {
        switch step {
        case .diets: selectedDiets.isEmpty
        case .likes: selectedLikes.isEmpty
        case .allergies: selectedAllergies.isEmpty
        default: false
        }
    }

    // MARK: - Steps

    private var welcomeStep: some View {
        VStack(spacing: 24) {
            Spacer()
            VStack(spacing: 10) {
                Text("Capy")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.capy.textPrimary)
                Text("A few quick answers so logging fits your day.")
                    .font(.body)
                    .foregroundStyle(Color.capy.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 28)
            }
            GlassPanel {
                VStack(alignment: .leading, spacing: 10) {
                    setupBullet("Daily calorie and macro targets")
                    setupBullet("How chatty Capy should be")
                    setupBullet("Diet, likes, and allergies")
                }
            }
            .padding(.horizontal, 24)
            Spacer()
        }
    }

    private func setupBullet(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(Color.capy.accent)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(Color.capy.textPrimary)
            Spacer(minLength: 0)
        }
    }

    private var caloriesStep: some View {
        questionScaffold(
            title: "About how many calories a day?",
            subtitle: "You can change this anytime in Settings."
        ) {
            GlassPanel {
                VStack(spacing: 20) {
                    Text("\(Int(calories.rounded()))")
                        .font(.system(size: 56, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.capy.budgetCalories)
                        .contentTransition(.numericText())
                        .animation(.snappy, value: calories)

                    HStack(spacing: 28) {
                        calorieAdjustButton(systemName: "minus", delta: -50)
                        calorieAdjustButton(systemName: "plus", delta: 50)
                    }

                    Text("kcal per day")
                        .font(.footnote)
                        .foregroundStyle(Color.capy.textSecondary)
                }
                .frame(maxWidth: .infinity)
            }
            .padding(.horizontal, 24)
        }
    }

    private func calorieAdjustButton(systemName: String, delta: Double) -> some View {
        Button {
            withAnimation(.snappy) {
                calories = min(10_000, max(0, calories + delta))
                applySplitIfNeeded()
            }
        } label: {
            Image(systemName: systemName)
                .font(.title2.weight(.semibold))
                .foregroundStyle(Color.capy.textPrimary)
                .frame(width: 56, height: 56)
                .background(Color.capy.accentSoft, in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(delta < 0 ? "Decrease calories" : "Increase calories")
    }

    private var macrosStep: some View {
        questionScaffold(
            title: "How do you like your macros?",
            subtitle: "We’ll fill protein, carbs, and fat from this."
        ) {
            ScrollView {
                VStack(spacing: 10) {
                    ForEach(MacroSplit.allCases) { option in
                        selectionCard(
                            title: option.title,
                            subtitle: option.subtitle,
                            selected: split == option
                        ) {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                split = option
                                applySplitIfNeeded()
                            }
                        }
                    }

                    if split == .custom {
                        GlassPanel {
                            VStack(spacing: 12) {
                                macroAdjustRow("Protein", value: $protein, color: Color.capy.budgetProtein)
                                macroAdjustRow("Carbs", value: $carbs, color: Color.capy.budgetCarbs)
                                macroAdjustRow("Fat", value: $fat, color: Color.capy.budgetFat)
                            }
                        }
                        .padding(.top, 4)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                    } else {
                        Text("\(Int(protein))g P · \(Int(carbs))g C · \(Int(fat))g F")
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(Color.capy.textSecondary)
                            .padding(.top, 4)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 8)
            }
        }
    }

    private func macroAdjustRow(_ title: String, value: Binding<Double>, color: Color) -> some View {
        HStack {
            Text(title)
                .foregroundStyle(Color.capy.textPrimary)
            Spacer()
            Text("\(Int(value.wrappedValue.rounded())) g")
                .foregroundStyle(color)
                .fontWeight(.semibold)
                .monospacedDigit()
            Stepper("", value: value, in: 0...500, step: 5)
                .labelsHidden()
        }
    }

    private var dialStep: some View {
        questionScaffold(
            title: "How should Capy show up?",
            subtitle: "This only changes how often Capy speaks first."
        ) {
            VStack(spacing: 10) {
                ForEach(AssistanceLevel.allCases) { level in
                    selectionCard(
                        title: level.title,
                        subtitle: level.subtitle,
                        selected: dial == level
                    ) {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            dial = level
                        }
                    }
                }
            }
            .padding(.horizontal, 24)
        }
    }

    private func chipStep(
        title: String,
        subtitle: String,
        options: [String],
        selection: Binding<Set<String>>
    ) -> some View {
        questionScaffold(title: title, subtitle: subtitle) {
            ScrollView {
                OnboardingChipGrid(options: options, selection: selection)
                    .padding(.horizontal, 24)
                    .padding(.bottom, 8)
            }
        }
    }

    private var readyStep: some View {
        VStack(spacing: 24) {
            Spacer()
            VStack(spacing: 10) {
                Text("You’re set")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.capy.textPrimary)
                Text(readySummary)
                    .font(.body)
                    .foregroundStyle(Color.capy.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            GlassPanel {
                VStack(alignment: .leading, spacing: 8) {
                    readyLine(label: "Calories", value: "\(Int(calories.rounded())) kcal")
                    readyLine(label: "Macros", value: "\(Int(protein)) / \(Int(carbs)) / \(Int(fat)) g")
                    readyLine(label: "Capy", value: dial.title)
                    if !selectedDiets.isEmpty {
                        readyLine(label: "Diet", value: selectedDiets.sorted().joined(separator: ", "))
                    }
                    if !selectedAllergies.isEmpty {
                        readyLine(label: "Allergies", value: selectedAllergies.sorted().joined(separator: ", "))
                    }
                }
            }
            .padding(.horizontal, 24)
            Spacer()
        }
    }

    private var readySummary: String {
        "\(Int(calories.rounded())) kcal · \(dial.title). Open the Food Log when you’re ready."
    }

    private func readyLine(label: String, value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(Color.capy.textSecondary)
            Spacer()
            Text(value)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Color.capy.textPrimary)
                .multilineTextAlignment(.trailing)
        }
    }

    // MARK: - Shared layout

    private func questionScaffold<Content: View>(
        title: String,
        subtitle: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text(title)
                    .font(.title2.weight(.bold))
                    .foregroundStyle(Color.capy.textPrimary)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textSecondary)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)

            content()
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }

    private func selectionCard(
        title: String,
        subtitle: String,
        selected: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(Color.capy.textPrimary)
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(Color.capy.textSecondary)
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(selected ? Color.capy.accent : Color.capy.textSecondary.opacity(0.5))
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Color.capy.surfaceElevated)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(selected ? Color.capy.accent : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .scaleEffect(selected ? 1.01 : 1)
        .animation(.easeInOut(duration: 0.18), value: selected)
    }

    // MARK: - Navigation

    private func goForward() {
        guard let next = OnboardingStep(rawValue: step.rawValue + 1) else { return }
        stepDirection = 1
        withAnimation(.easeInOut(duration: 0.28)) {
            step = next
        }
    }

    private func goBack() {
        guard let prev = OnboardingStep(rawValue: step.rawValue - 1) else { return }
        stepDirection = -1
        withAnimation(.easeInOut(duration: 0.28)) {
            step = prev
        }
    }

    // MARK: - Persist

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
        for allergy in selectedAllergies.sorted() {
            modelContext.insert(UserPreference(kind: .allergy, value: allergy))
        }
    }
}

// MARK: - Chips

private struct OnboardingChipGrid: View {
    let options: [String]
    @Binding var selection: Set<String>

    private let columns = [GridItem(.adaptive(minimum: 112), spacing: 8)]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
            ForEach(options, id: \.self) { option in
                let selected = selection.contains(option)
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        if selected {
                            selection.remove(option)
                        } else {
                            selection.insert(option)
                        }
                    }
                } label: {
                    Text(option)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Color.capy.textPrimary)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .frame(maxWidth: .infinity)
                        .background(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(selected ? Color.capy.accentSoft : Color.capy.surfaceElevated)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .strokeBorder(selected ? Color.capy.accent : Color.clear, lineWidth: 1.5)
                        )
                }
                .buttonStyle(.plain)
            }
        }
    }
}
