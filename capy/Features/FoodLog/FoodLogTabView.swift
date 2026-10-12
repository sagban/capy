import SwiftUI
import SwiftData

struct FoodLogTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \MealEntry.timestamp, order: .reverse) private var entries: [MealEntry]
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]

    @State private var selectedDay = Calendar.current.startOfDay(for: .now)
    @State private var showInsights = false
    @State private var showManualLog = false

    private var dayKey: String { DayKey.make(from: selectedDay) }

    private var dayEntries: [MealEntry] {
        entries.filter { $0.dayKey == dayKey && $0.confirmed }
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

    private var remaining: MacroTotals {
        MacroTotals.remaining(target: target, eaten: eaten)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                List {
                    Section {
                        HStack {
                            Button {
                                selectedDay = Calendar.current.date(byAdding: .day, value: -1, to: selectedDay) ?? selectedDay
                            } label: {
                                Image(systemName: "chevron.left")
                            }
                            Spacer()
                            Text(selectedDay, format: .dateTime.month().day().year())
                                .fontWeight(.semibold)
                            Spacer()
                            Button {
                                selectedDay = Calendar.current.date(byAdding: .day, value: 1, to: selectedDay) ?? selectedDay
                            } label: {
                                Image(systemName: "chevron.right")
                            }
                        }
                        .buttonStyle(.plain)

                        VStack(alignment: .leading, spacing: 6) {
                            Text("Goals")
                                .font(.caption)
                                .foregroundStyle(Color.capy.textSecondary)
                            Text("\(Int(eaten.calories)) / \(Int(target.calories)) cal")
                                .font(.title3.weight(.semibold))
                                .foregroundStyle(Color.capy.budgetCalories)
                            Text("P \(Int(eaten.proteinG))/\(Int(target.proteinG)) · C \(Int(eaten.carbsG))/\(Int(target.carbsG)) · F \(Int(eaten.fatG))/\(Int(target.fatG))")
                                .font(.subheadline)
                                .foregroundStyle(Color.capy.textSecondary)
                            if eaten.calories > target.calories {
                                Text("0 left · over target")
                                    .font(.footnote)
                                    .foregroundStyle(Color.capy.warning)
                            } else {
                                Text("\(Int(remaining.calories)) cal left")
                                    .font(.footnote)
                                    .foregroundStyle(Color.capy.textSecondary)
                            }
                        }
                        .listRowBackground(Color.capy.surface.opacity(0.001))
                    }

                    Section("Logged") {
                        if dayEntries.isEmpty {
                            Text("nothing logged this day yet")
                                .foregroundStyle(Color.capy.textSecondary)
                        } else {
                            ForEach(dayEntries) { entry in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(entry.originalUserText ?? entry.items.first?.name ?? "Meal")
                                        .font(.headline)
                                    Text("\(Int(entry.calories)) cal · P \(Int(entry.proteinG)) · C \(Int(entry.carbsG)) · F \(Int(entry.fatG))")
                                        .font(.subheadline)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                            }
                            .onDelete(perform: delete)
                        }
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Food Log")
            .toolbar {
                SettingsToolbarButton()
                ToolbarItem(placement: .topBarLeading) {
                    Button("Insights") { showInsights = true }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showManualLog = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("Add food")
                }
            }
            .sheet(isPresented: $showInsights) {
                InsightsSheet(entries: entries, targetCalories: target.calories)
                    .presentationDetents([.medium])
            }
            .sheet(isPresented: $showManualLog) {
                ManualLogSheet(dayKey: dayKey)
                    .presentationDetents([.medium, .large])
            }
        }
    }

    private func delete(at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(dayEntries[index])
        }
    }
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
