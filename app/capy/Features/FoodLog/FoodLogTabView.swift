import SwiftUI
import SwiftData

struct FoodLogTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.unitPreferences) private var units
    @Query(sort: \MealEntry.timestamp, order: .reverse) private var entries: [MealEntry]
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    @State private var selectedDay = Calendar.current.startOfDay(for: .now)
    @State private var showInsights = false
    @State private var logSheet: LogSheetRequest?
    @State private var editingEntry: MealEntry?
    @State private var selectedGoalMetric: GoalMetric?

    private let pageInset: CGFloat = 16

    private var dayKey: String { DayKey.make(from: selectedDay) }

    private var dayEntries: [MealEntry] {
        entries.filter { $0.dayKey == dayKey && $0.confirmed }
    }

    private var enabledMealTypes: [MealType] {
        mealTypes.filter(\.isEnabled)
    }

    private var target: MacroTotals {
        let t = targets.first
        return MacroTotals(
            calories: t?.calories ?? 2000,
            proteinG: t?.proteinG ?? 140,
            carbsG: t?.carbsG ?? 200,
            fatG: t?.fatG ?? 65
        )
    }

    private var eaten: MacroTotals {
        dayEntries.reduce(.zero) { partial, entry in
            MacroTotals(
                calories: partial.calories + entry.calories,
                proteinG: partial.proteinG + entry.proteinG,
                carbsG: partial.carbsG + entry.carbsG,
                fatG: partial.fatG + entry.fatG
            )
        }
    }

    private var knownSlotNames: Set<String> {
        Set(enabledMealTypes.map(\.name))
    }

    private var uncategorizedEntries: [MealEntry] {
        dayEntries.filter { entry in
            guard let slot = entry.mealSlot, !slot.isEmpty else { return true }
            return !knownSlotNames.contains(slot)
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                // List keeps native swipe-to-delete; goals stay a clear header row.
                List {
                    Section {
                        dayGoalsHeader
                            // Match meal card width — no extra inset on top of insetGrouped margins.
                            .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 12, trailing: 0))
                            .listRowBackground(Color.clear)
                            .listRowSeparator(.hidden)
                    }

                    ForEach(enabledMealTypes) { type in
                        mealSection(
                            title: type.name,
                            entries: dayEntries.filter { $0.mealSlot == type.name }
                        ) {
                            logSheet = LogSheetRequest(mealSlot: type.name)
                        }
                    }

                    if !uncategorizedEntries.isEmpty {
                        mealSection(title: "Other", entries: uncategorizedEntries) {
                            logSheet = LogSheetRequest(mealSlot: nil)
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .listSectionSpacing(18)
                .scrollContentBackground(.hidden)
                .scrollDismissesKeyboard(.interactively)
                .animation(.easeInOut(duration: 0.22), value: dayKey)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    DayNavigator(selectedDay: $selectedDay, compact: true)
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showInsights = true
                    } label: {
                        Image(systemName: "chart.bar.xaxis")
                    }
                    .accessibilityLabel("Insights")

                    NavigationLink {
                        SettingsRootView()
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel("Settings")
                }
            }
            .sheet(isPresented: $showInsights) {
                InsightsSheet(entries: entries, target: target)
                    .presentationDetents([.medium, .large])
            }
            .sheet(item: $logSheet) { request in
                ManualLogSheet(initialDay: selectedDay, initialMealSlot: request.mealSlot)
                    .presentationDetents([.large])
            }
            .sheet(item: $editingEntry) { entry in
                EditMealEntrySheet(entry: entry)
                    .presentationDetents([.large])
            }
            .sheet(item: $selectedGoalMetric) { metric in
                GoalDetailView(metric: metric)
                    .presentationDetents([.large])
            }
            .onAppear {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
            }
        }
    }

    private var dayGoalsHeader: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Goals")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.capy.textSecondary)

            GoalsGridView(eaten: eaten, target: target) { metric in
                selectedGoalMetric = metric
            }
        }
        .padding(.horizontal, pageInset)
    }

    @ViewBuilder
    private func mealSection(
        title: String,
        entries: [MealEntry],
        onAdd: @escaping () -> Void
    ) -> some View {
        Section {
            ForEach(entries) { entry in
                Button {
                    editingEntry = entry
                } label: {
                    mealRow(entry)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .listRowInsets(EdgeInsets(top: 12, leading: pageInset, bottom: 12, trailing: pageInset))
                .listRowBackground(Color.capy.surface)
                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                    Button("Delete", role: .destructive) {
                        modelContext.delete(entry)
                    }
                }
            }

            Button(action: onAdd) {
                HStack(spacing: 10) {
                    Image(systemName: "plus")
                        .font(.body.weight(.semibold))
                    Text("Add to \(title)")
                        .font(.body.weight(.medium))
                    Spacer(minLength: 0)
                }
                .foregroundStyle(Color.capy.accent)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .listRowInsets(EdgeInsets(top: 14, leading: pageInset, bottom: 14, trailing: pageInset))
            .listRowBackground(Color.capy.surface)
            .accessibilityLabel("Add to \(title)")
        } header: {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.capy.textSecondary)
                .textCase(nil)
        }
    }

    @ViewBuilder
    private func mealRow(_ entry: MealEntry) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            let names = entry.items.map { ReadableFoodName.display($0.name) }.filter { !$0.isEmpty }
            Text(names.isEmpty ? (entry.originalUserText ?? "Meal") : names.joined(separator: ", "))
                .font(.headline)
                .foregroundStyle(Color.capy.textPrimary)
            ForEach(Array(entry.items.enumerated()), id: \.offset) { _, item in
                Text("\(Int(item.grams)) g  \(ReadableFoodName.display(item.name))")
                    .font(.caption)
                    .foregroundStyle(Color.capy.textSecondary)
            }
            FoodMacroBadgeRow(
                calories: entry.calories,
                carbsG: entry.carbsG,
                fatG: entry.fatG,
                proteinG: entry.proteinG
            )
        }
    }
}

private struct LogSheetRequest: Identifiable {
    let id = UUID()
    let mealSlot: String?
}

struct InsightsSheet: View {
    @Environment(\.unitPreferences) private var units

    let entries: [MealEntry]
    let target: MacroTotals

    private var week: [InsightDay] {
        (0..<7).reversed().compactMap { offset in
            guard let day = Calendar.current.date(byAdding: .day, value: -offset, to: .now) else { return nil }
            let key = DayKey.make(from: day)
            let logged = entries.filter { $0.dayKey == key && $0.confirmed }
            let eaten = logged.reduce(MacroTotals.zero) { partial, entry in
                MacroTotals(
                    calories: partial.calories + entry.calories,
                    proteinG: partial.proteinG + entry.proteinG,
                    carbsG: partial.carbsG + entry.carbsG,
                    fatG: partial.fatG + entry.fatG
                )
            }
            let label = day.formatted(.dateTime.weekday(.narrow))
            return InsightDay(key: key, label: label, eaten: eaten, meals: logged)
        }
    }

    private var loggedDays: [InsightDay] {
        week.filter { $0.eaten.calories > 0 }
    }

    private var average: MacroTotals {
        guard !loggedDays.isEmpty else { return .zero }
        let count = Double(loggedDays.count)
        let sum = loggedDays.reduce(MacroTotals.zero) { $0 + $1.eaten }
        return MacroTotals(
            calories: sum.calories / count,
            proteinG: sum.proteinG / count,
            carbsG: sum.carbsG / count,
            fatG: sum.fatG / count
        )
    }

    private var topFoods: [(name: String, count: Int)] {
        var counts: [String: Int] = [:]
        for day in week {
            for entry in day.meals {
                for item in entry.items {
                    let name = ReadableFoodName.display(item.name)
                    guard !name.isEmpty else { continue }
                    counts[name, default: 0] += 1
                }
            }
        }
        return counts.sorted { lhs, rhs in
            if lhs.value == rhs.value { return lhs.key < rhs.key }
            return lhs.value > rhs.value
        }
        .prefix(5)
        .map { ($0.key, $0.value) }
    }

    private var slots: [(name: String, calories: Double)] {
        var totals: [String: Double] = [:]
        for day in week {
            for entry in day.meals {
                let name = (entry.mealSlot?.isEmpty == false) ? entry.mealSlot! : "Other"
                totals[name, default: 0] += entry.calories
            }
        }
        return totals.sorted { $0.value > $1.value }.map { ($0.key, $0.value) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    WeekCalorieBars(days: week, target: target.calories)
                        .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))
                    LabeledContent("Days with a log", value: "\(loggedDays.count) of 7")
                    LabeledContent("Avg energy", value: units.formattedEnergy(average.calories))
                    LabeledContent("Target", value: units.formattedEnergy(target.calories))
                } header: {
                    Text("Last 7 days")
                }

                Section("Avg macros on logged days") {
                    macroLine("Protein", grams: average.proteinG, target: target.proteinG, color: Color.capy.budgetProtein)
                    macroLine("Carbs", grams: average.carbsG, target: target.carbsG, color: Color.capy.budgetCarbs)
                    macroLine("Fat", grams: average.fatG, target: target.fatG, color: Color.capy.budgetFat)
                }

                Section("Foods") {
                    if topFoods.isEmpty {
                        Text("No foods logged in these 7 days.")
                            .foregroundStyle(Color.capy.textSecondary)
                    } else {
                        ForEach(topFoods, id: \.name) { food in
                            LabeledContent(food.name, value: "\(food.count)")
                        }
                    }
                }

                Section("By meal") {
                    if slots.isEmpty {
                        Text("No meals logged in these 7 days.")
                            .foregroundStyle(Color.capy.textSecondary)
                    } else {
                        ForEach(slots, id: \.name) { slot in
                            LabeledContent(slot.name, value: units.formattedEnergy(slot.calories))
                        }
                    }
                }
            }
            .navigationTitle("Insights")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func macroLine(_ title: String, grams: Double, target: Double, color: Color) -> some View {
        LabeledContent {
            Text("\(Int(grams.rounded())) / \(Int(target.rounded())) g")
                .foregroundStyle(color)
        } label: {
            Text(title)
        }
    }
}

private struct InsightDay {
    let key: String
    let label: String
    let eaten: MacroTotals
    let meals: [MealEntry]
}

private struct WeekCalorieBars: View {
    let days: [InsightDay]
    let target: Double

    var body: some View {
        let peak = max(target, days.map(\.eaten.calories).max() ?? 0, 1)
        HStack(alignment: .bottom, spacing: 8) {
            ForEach(days, id: \.key) { day in
                VStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .fill(day.eaten.calories > target && target > 0 ? Color.capy.warning : Color.capy.budgetCalories)
                        .frame(height: barHeight(day.eaten.calories, peak: peak))
                    Text(day.label)
                        .font(.caption2)
                        .foregroundStyle(Color.capy.textSecondary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .frame(height: 148)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Calories for the last 7 days")
    }

    private func barHeight(_ calories: Double, peak: Double) -> CGFloat {
        guard calories > 0 else { return 4 }
        return max(8, 112 * calories / peak)
    }
}
