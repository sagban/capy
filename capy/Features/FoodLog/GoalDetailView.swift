import Charts
import SwiftData
import SwiftUI

enum GoalMetric: String, CaseIterable, Identifiable {
    case calories
    case protein
    case carbs
    case fat

    var id: String { rawValue }

    func title(units: UnitPreferences) -> String {
        switch self {
        case .calories: units.energy.goalTitle
        case .protein: "Protein"
        case .carbs: "Carbohydrates"
        case .fat: "Fat"
        }
    }

    func unitSuffix(units: UnitPreferences) -> String {
        switch self {
        case .calories: units.energy.shortLabel
        case .protein, .carbs, .fat: "g"
        }
    }

    var color: Color {
        switch self {
        case .calories: Color.capy.budgetCalories
        case .protein: Color.capy.budgetProtein
        case .carbs: Color.capy.budgetCarbs
        case .fat: Color.capy.budgetFat
        }
    }

    var symbolName: String {
        switch self {
        case .calories: "flame.fill"
        case .protein: "dumbbell.fill"
        case .carbs: "carrot.fill"
        case .fat: "drop.fill"
        }
    }

    func value(from totals: MacroTotals, units: UnitPreferences) -> Double {
        switch self {
        case .calories: units.energy(fromKcal: totals.calories)
        case .protein: totals.proteinG
        case .carbs: totals.carbsG
        case .fat: totals.fatG
        }
    }

    func value(from entry: MealEntry, units: UnitPreferences) -> Double {
        value(
            from: MacroTotals(
                calories: entry.calories,
                proteinG: entry.proteinG,
                carbsG: entry.carbsG,
                fatG: entry.fatG
            ),
            units: units
        )
    }

    func value(from item: MealEntryItem, units: UnitPreferences) -> Double {
        value(
            from: MacroTotals(
                calories: item.calories,
                proteinG: item.proteinG,
                carbsG: item.carbsG,
                fatG: item.fatG
            ),
            units: units
        )
    }

    func targetValue(from target: MacroTotals, units: UnitPreferences) -> Double {
        value(from: target, units: units)
    }
}

enum GoalChartRange: String, CaseIterable, Identifiable {
    case day
    case week
    case month

    var id: String { rawValue }

    var title: String {
        switch self {
        case .day: "Day"
        case .week: "Week"
        case .month: "Month"
        }
    }
}

struct GoalBucket: Identifiable {
    let id: Date
    let value: Double
    let hasData: Bool
    let isCurrent: Bool
}

struct GoalDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.unitPreferences) private var units
    @Query(sort: \MealEntry.timestamp, order: .reverse) private var entries: [MealEntry]
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]

    let metric: GoalMetric

    @State private var range: GoalChartRange = .week

    private var confirmedEntries: [MealEntry] {
        entries.filter(\.confirmed)
    }

    private var buckets: [GoalBucket] {
        switch range {
        case .day: dayBuckets()
        case .week: weekBuckets()
        case .month: monthBuckets()
        }
    }

    private var averageExcludingIncomplete: Double {
        let cal = Calendar.current
        let today = cal.startOfDay(for: .now)
        let completed = buckets.filter { bucket in
            bucket.hasData && !cal.isDate(bucket.id, inSameDayAs: today)
        }
        // Day range: average across hours that have data (today's hours still count).
        if range == .day {
            let withData = buckets.filter(\.hasData)
            guard !withData.isEmpty else { return 0 }
            return withData.map(\.value).reduce(0, +) / Double(withData.count)
        }
        guard !completed.isEmpty else {
            let withData = buckets.filter(\.hasData)
            guard !withData.isEmpty else { return 0 }
            return withData.map(\.value).reduce(0, +) / Double(withData.count)
        }
        return completed.map(\.value).reduce(0, +) / Double(completed.count)
    }

    private var totalForRange: Double {
        buckets.map(\.value).reduce(0, +)
    }

    private var headlineValue: Double {
        range == .day ? totalForRange : averageExcludingIncomplete
    }

    private var headlineLabel: String {
        range == .day ? "TOTAL" : "AVERAGE"
    }

    private var dateRangeText: String {
        guard let first = buckets.first?.id, let last = buckets.last?.id else { return "" }
        let cal = Calendar.current
        if range == .day {
            if cal.isDateInToday(first) { return "Today" }
            if cal.isDateInYesterday(first) { return "Yesterday" }
            return first.formatted(.dateTime.month(.abbreviated).day().year())
        }
        let endLabel = cal.isDateInToday(last) ? "Today" : last.formatted(.dateTime.month(.abbreviated).day())
        return "\(first.formatted(.dateTime.month(.abbreviated).day())) – \(endLabel)"
    }

    private var goalLine: Double {
        metric.targetValue(from: currentTarget, units: units)
    }

    private var currentTarget: MacroTotals {
        targetTotals(on: .now)
    }

    private var daysMet: Int {
        guard range != .day else {
            return totalForRange > 0 && totalForRange <= goalLine ? 1 : 0
        }
        return buckets.filter { $0.hasData && $0.value <= goalLine }.count
    }

    private var trendPercent: Int? {
        guard range != .day else { return nil }
        let previous = previousPeriodAverage()
        guard previous > 0, averageExcludingIncomplete > 0 else { return nil }
        let delta = ((averageExcludingIncomplete - previous) / previous) * 100
        return Int(delta.rounded())
    }

    private var topFoods: [(name: String, amount: Double)] {
        let keys = Set(dayKeysInRange())
        var totals: [String: Double] = [:]
        for entry in confirmedEntries where keys.contains(entry.dayKey) {
            for item in entry.items {
                let amount = metric.value(from: item, units: units)
                guard amount > 0 else { continue }
                totals[item.name, default: 0] += amount
            }
        }
        return totals
            .map { (name: $0.key, amount: $0.value) }
            .sorted { $0.amount > $1.amount }
            .prefix(5)
            .map { $0 }
    }

    private var chartYMax: Double {
        let peak = max(buckets.map(\.value).max() ?? 0, goalLine)
        guard peak > 0 else { return 100 }
        let padded = peak * 1.15
        let step = niceStep(for: padded)
        return ceil(padded / step) * step
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        Picker("Range", selection: $range) {
                            ForEach(GoalChartRange.allCases) { option in
                                Text(option.title).tag(option)
                            }
                        }
                        .pickerStyle(.segmented)

                        summaryHeader

                        chartCard

                        statsRows

                        topFoodsSection
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                }
            }
            .navigationTitle(metric.title(units: units))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                    .accessibilityLabel("Close")
                }
            }
        }
    }

    private var summaryHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(headlineLabel)
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.capy.textSecondary)
                .tracking(0.6)

            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text("\(formatted(headlineValue))\(metric.unitSuffix(units: units))")
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.capy.textPrimary)
                    .minimumScaleFactor(0.7)
                    .lineLimit(1)

                if let trendPercent {
                    HStack(spacing: 2) {
                        Image(systemName: trendPercent >= 0 ? "arrow.up" : "arrow.down")
                        Text("\(abs(trendPercent))%")
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(trendPercent >= 0 ? Color.capy.accent : Color.capy.warning)
                }
            }

            Text(dateRangeText)
                .font(.subheadline)
                .foregroundStyle(Color.capy.textSecondary)
        }
        .accessibilityElement(children: .combine)
    }

    private var chartCard: some View {
        Chart {
            if goalLine > 0 {
                RuleMark(y: .value("Goal", goalLine))
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [5, 4]))
                    .foregroundStyle(metric.color.opacity(0.85))
            }

            ForEach(buckets) { bucket in
                BarMark(
                    x: .value("Period", bucket.id, unit: xUnit),
                    y: .value(metric.title(units: units), bucket.value)
                )
                .foregroundStyle(bucket.isCurrent ? metric.color : Color.capy.textSecondary.opacity(0.35))
                .cornerRadius(3)
            }
        }
        .chartYScale(domain: 0...chartYMax)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                    .foregroundStyle(Color.capy.textSecondary.opacity(0.25))
                AxisValueLabel {
                    if let v = value.as(Double.self) {
                        Text(formatted(v))
                            .font(.caption2)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
            }
        }
        .chartXAxis {
            AxisMarks(values: xAxisDates) { value in
                AxisValueLabel {
                    if let date = value.as(Date.self) {
                        Text(xLabel(for: date))
                            .font(.caption2)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
            }
        }
        .frame(height: 220)
        .padding(.top, 8)
        .accessibilityLabel("\(metric.title(units: units)) chart for \(range.title.lowercased())")
    }

    private var xUnit: Calendar.Component {
        range == .day ? .hour : .day
    }

    private var xAxisDates: [Date] {
        switch range {
        case .day:
            buckets.filter { Calendar.current.component(.hour, from: $0.id) % 6 == 0 }.map(\.id)
        case .week:
            buckets.map(\.id)
        case .month:
            buckets.enumerated().compactMap { index, bucket in
                index % 5 == 0 || bucket.isCurrent ? bucket.id : nil
            }
        }
    }

    private func xLabel(for date: Date) -> String {
        switch range {
        case .day:
            let hour = Calendar.current.component(.hour, from: date)
            if hour == 0 { return "12a" }
            if hour < 12 { return "\(hour)a" }
            if hour == 12 { return "12p" }
            return "\(hour - 12)p"
        case .week:
            return date.formatted(.dateTime.weekday(.narrow))
        case .month:
            return date.formatted(.dateTime.day())
        }
    }

    private var statsRows: some View {
        VStack(spacing: 10) {
            statRow(
                title: "Goal",
                value: range == .day
                    ? "\(formatted(goalLine)) \(metric.unitSuffix(units: units))"
                    : "\(daysMet) Day\(daysMet == 1 ? "" : "s") Met",
                emphasized: true
            )
            if range != .day {
                statRow(title: "Moving Average", value: movingAverageLabel, emphasized: false)
            }
            Text("Averages exclude today and days without data.")
                .font(.caption)
                .foregroundStyle(Color.capy.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 2)
        }
    }

    private var movingAverageLabel: String {
        switch range {
        case .day: "—"
        case .week: "7 Days"
        case .month: "30 Days"
        }
    }

    private func statRow(title: String, value: String, emphasized: Bool) -> some View {
        HStack {
            Text(title)
                .font(.subheadline.weight(.semibold))
            Spacer()
            Text(value)
                .font(.subheadline.weight(.semibold))
        }
        .foregroundStyle(emphasized ? Color.white : Color.capy.textPrimary)
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            emphasized ? metric.color.opacity(0.92) : Color.capy.surfaceElevated.opacity(0.92),
            in: Capsule()
        )
    }

    private var topFoodsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Top Foods")
                .font(.title3.weight(.bold))
                .foregroundStyle(Color.capy.textPrimary)

            if topFoods.isEmpty {
                Text("Log meals to see which foods add the most \(metric.title(units: units).lowercased()).")
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textSecondary)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.capy.surfaceElevated.opacity(0.92), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(topFoods.enumerated()), id: \.element.name) { index, food in
                        HStack {
                            Text(food.name)
                                .font(.body.weight(.medium))
                                .foregroundStyle(Color.capy.textPrimary)
                            Spacer()
                            Text("\(formatted(food.amount)) \(metric.unitSuffix(units: units))")
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(metric.color)
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        if index < topFoods.count - 1 {
                            Divider().opacity(0.35)
                        }
                    }
                }
                .background(Color.capy.surfaceElevated.opacity(0.92), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Buckets

    private func dayBuckets() -> [GoalBucket] {
        let cal = Calendar.current
        let day = cal.startOfDay(for: .now)
        let dayEntries = confirmedEntries.filter { $0.dayKey == DayKey.make(from: day) }
        let currentHour = cal.component(.hour, from: .now)

        return (0..<24).compactMap { hour -> GoalBucket? in
            guard let start = cal.date(bySettingHour: hour, minute: 0, second: 0, of: day) else { return nil }
            let value = dayEntries
                .filter { cal.component(.hour, from: $0.timestamp) == hour }
                .reduce(0) { $0 + metric.value(from: $1, units: units) }
            return GoalBucket(
                id: start,
                value: value,
                hasData: value > 0,
                isCurrent: hour == currentHour
            )
        }
    }

    private func weekBuckets() -> [GoalBucket] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: .now)
        return (0..<7).reversed().compactMap { offset -> GoalBucket? in
            guard let day = cal.date(byAdding: .day, value: -offset, to: today) else { return nil }
            let totals = totals(on: day)
            let value = metric.value(from: totals, units: units)
            return GoalBucket(
                id: day,
                value: value,
                hasData: value > 0,
                isCurrent: offset == 0
            )
        }
    }

    private func monthBuckets() -> [GoalBucket] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: .now)
        return (0..<30).reversed().compactMap { offset -> GoalBucket? in
            guard let day = cal.date(byAdding: .day, value: -offset, to: today) else { return nil }
            let totals = totals(on: day)
            let value = metric.value(from: totals, units: units)
            return GoalBucket(
                id: day,
                value: value,
                hasData: value > 0,
                isCurrent: offset == 0
            )
        }
    }

    private func dayKeysInRange() -> [String] {
        switch range {
        case .day:
            return [DayKey.make(from: .now)]
        case .week, .month:
            return buckets.map { DayKey.make(from: $0.id) }
        }
    }

    private func totals(on day: Date) -> MacroTotals {
        let key = DayKey.make(from: day)
        return confirmedEntries
            .filter { $0.dayKey == key }
            .reduce(.zero) { partial, entry in
                MacroTotals(
                    calories: partial.calories + entry.calories,
                    proteinG: partial.proteinG + entry.proteinG,
                    carbsG: partial.carbsG + entry.carbsG,
                    fatG: partial.fatG + entry.fatG
                )
            }
    }

    private func targetTotals(on day: Date) -> MacroTotals {
        let start = Calendar.current.startOfDay(for: day)
        let match = targets.first { Calendar.current.startOfDay(for: $0.effectiveDate) <= start }
        return MacroTotals(
            calories: match?.calories ?? 2000,
            proteinG: match?.proteinG ?? 140,
            carbsG: match?.carbsG ?? 200,
            fatG: match?.fatG ?? 65
        )
    }

    private func previousPeriodAverage() -> Double {
        let cal = Calendar.current
        let today = cal.startOfDay(for: .now)
        let length = range == .week ? 7 : 30
        var values: [Double] = []
        for offset in length..<(length * 2) {
            guard let day = cal.date(byAdding: .day, value: -offset, to: today) else { continue }
            let value = metric.value(from: totals(on: day), units: units)
            if value > 0 { values.append(value) }
        }
        guard !values.isEmpty else { return 0 }
        return values.reduce(0, +) / Double(values.count)
    }

    private func formatted(_ value: Double) -> String {
        "\(Int(value.rounded()))"
    }

    private func niceStep(for maxValue: Double) -> Double {
        switch maxValue {
        case ..<50: 10
        case ..<150: 25
        case ..<400: 50
        case ..<1000: 100
        case ..<2500: 250
        default: 500
        }
    }
}
