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
                InsightsSheet(entries: entries, targetCalories: target.calories)
                    .presentationDetents([.medium])
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
            Text(entry.originalUserText ?? entry.items.first?.name ?? "Meal")
                .font(.headline)
                .foregroundStyle(Color.capy.textPrimary)
            let itemLine = entry.items.map(\.name).joined(separator: " · ")
            if !itemLine.isEmpty, itemLine != (entry.originalUserText ?? "") {
                Text(itemLine)
                    .font(.caption)
                    .foregroundStyle(Color.capy.textSecondary)
                    .lineLimit(1)
            }
            HStack(spacing: 10) {
                macroBadge("flame.fill", units.formattedEnergy(entry.calories), Color.capy.budgetCalories)
                macroBadge("circle.fill", "C \(Int(entry.carbsG))", Color.capy.budgetCarbs)
                macroBadge("circle.fill", "F \(Int(entry.fatG))", Color.capy.budgetFat)
                macroBadge("circle.fill", "P \(Int(entry.proteinG))", Color.capy.budgetProtein)
            }
        }
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
}

private struct LogSheetRequest: Identifiable {
    let id = UUID()
    let mealSlot: String?
}

struct InsightsSheet: View {
    let entries: [MealEntry]
    let targetCalories: Double

    private var last7Keys: [String] {
        (0..<7).compactMap { offset in
            guard let day = Calendar.current.date(byAdding: .day, value: -offset, to: .now) else { return nil }
            return DayKey.make(from: day)
        }
    }

    private var daysLogged: Int {
        Set(entries.filter { last7Keys.contains($0.dayKey) && $0.confirmed }.map(\.dayKey)).count
    }

    private var weekAverage: Double {
        let keys = last7Keys
        let totals = keys.map { key in
            entries.filter { $0.dayKey == key && $0.confirmed }.reduce(0) { $0 + $1.calories }
        }
        let logged = totals.filter { $0 > 0 }
        guard !logged.isEmpty else { return 0 }
        return logged.reduce(0, +) / Double(logged.count)
    }

    var body: some View {
        NavigationStack {
            List {
                LabeledContent("Days logged (7d)", value: "\(daysLogged)")
                LabeledContent("Avg calories on logged days", value: "\(Int(weekAverage.rounded()))")
                LabeledContent("Daily target", value: "\(Int(targetCalories))")
                Text("Full charts come later.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .navigationTitle("Insights")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
