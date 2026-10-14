import SwiftUI
import UIKit

struct CapyScreenBackground: View {
    var body: some View {
        Color.capy.background
            .ignoresSafeArea()
    }
}

struct GlassPanel<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        content()
            .padding()
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct SettingsToolbarButton: ToolbarContent {
    var body: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            NavigationLink {
                SettingsRootView()
            } label: {
                Image(systemName: "gearshape")
            }
            .accessibilityLabel("Settings")
        }
    }
}

enum Keyboard {
    static func dismiss() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder),
            to: nil,
            from: nil,
            for: nil
        )
    }
}

extension View {
    /// Adds a keyboard toolbar Done button so decimal pads can be dismissed.
    func keyboardDoneToolbar() -> some View {
        toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done") { Keyboard.dismiss() }
            }
        }
    }
}

/// Food Log goals — four rings in a row, % centered, title below.
struct GoalsGridView: View {
    @Environment(\.unitPreferences) private var units

    let eaten: MacroTotals
    let target: MacroTotals
    var onSelect: (GoalMetric) -> Void = { _ in }

    var body: some View {
        HStack(spacing: 8) {
            GoalRingColumn(
                title: units.energy == .kilojoule ? "Energy" : "Calories",
                eaten: units.energy(fromKcal: eaten.calories),
                target: units.energy(fromKcal: target.calories),
                unitSuffix: units.energy.shortLabel,
                color: Color.capy.budgetCalories
            ) {
                onSelect(.calories)
            }
            GoalRingColumn(
                title: "Protein",
                eaten: eaten.proteinG,
                target: target.proteinG,
                unitSuffix: "g",
                color: Color.capy.budgetProtein
            ) {
                onSelect(.protein)
            }
            GoalRingColumn(
                title: "Carbs",
                eaten: eaten.carbsG,
                target: target.carbsG,
                unitSuffix: "g",
                color: Color.capy.budgetCarbs
            ) {
                onSelect(.carbs)
            }
            GoalRingColumn(
                title: "Fat",
                eaten: eaten.fatG,
                target: target.fatG,
                unitSuffix: "g",
                color: Color.capy.budgetFat
            ) {
                onSelect(.fat)
            }
        }
    }
}

private struct GoalRingColumn: View {
    let title: String
    let eaten: Double
    let target: Double
    let unitSuffix: String
    let color: Color
    let action: () -> Void

    private var ratio: Double {
        guard target > 0 else { return 0 }
        return max(0, eaten / target)
    }

    private var ringProgress: Double { min(1, ratio) }

    private var percentText: String {
        "\(Int((ratio * 100).rounded()))%"
    }

    private var remaining: Double { max(0, target - eaten) }
    private var over: Double { max(0, eaten - target) }

    private var status: String {
        if over > 0 {
            return "\(Int(over.rounded())) \(unitSuffix) over"
        }
        if remaining == 0 {
            return "on target"
        }
        return "\(Int(remaining.rounded())) \(unitSuffix) left"
    }

    private var amountUnder: String {
        if over > 0 {
            return "\(Int(over.rounded())) \(unitSuffix)"
        }
        return "\(Int(remaining.rounded())) \(unitSuffix)"
    }

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .stroke(color.opacity(0.22), lineWidth: 8)
                    Circle()
                        .trim(from: 0, to: ringProgress)
                        .stroke(color, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    Text(percentText)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(over > 0 ? Color.capy.warning : Color.capy.textPrimary)
                        .minimumScaleFactor(0.65)
                        .lineLimit(1)
                        .padding(.horizontal, 4)
                }
                .frame(width: 72, height: 72)

                VStack(spacing: 2) {
                    Text(title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.capy.textSecondary)
                    Text(amountUnder)
                        .font(.caption.weight(.medium))
                        .foregroundStyle(over > 0 ? Color.capy.warning : Color.capy.textPrimary)
                }
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title), \(percentText), \(status)")
        .accessibilityHint("Shows \(title) chart")
    }
}

/// WHOOP-style day navigator: ‹ Today › — tap the label for a calendar.
struct DayNavigator: View {
    @Environment(\.unitPreferences) private var units
    @Binding var selectedDay: Date

    /// Compact control for the navigation bar leading slot.
    var compact: Bool = false

    @State private var showCalendar = false

    private var calendar: Calendar {
        var cal = Calendar.current
        cal.firstWeekday = units.firstWeekday
        return cal
    }

    private var title: String {
        if calendar.isDateInToday(selectedDay) { return "Today" }
        if calendar.isDateInYesterday(selectedDay) { return "Yesterday" }
        if calendar.isDateInTomorrow(selectedDay) { return "Tomorrow" }
        return selectedDay.formatted(.dateTime.weekday(.abbreviated).month(.abbreviated).day())
    }

    var body: some View {
        HStack(spacing: compact ? 2 : 0) {
            Button {
                shift(by: -1)
            } label: {
                Image(systemName: "chevron.left")
                    .font(compact ? .subheadline.weight(.semibold) : .body.weight(.semibold))
                    .frame(width: compact ? 28 : 44, height: compact ? 32 : 44)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("Previous day")

            Button {
                showCalendar = true
            } label: {
                Text(title)
                    .font(compact ? .subheadline.weight(.semibold) : .headline.weight(.semibold))
                    .foregroundStyle(Color.capy.textPrimary)
                    .lineLimit(1)
                    .padding(.horizontal, compact ? 2 : 0)
                    .padding(.vertical, compact ? 6 : 10)
                    .frame(maxWidth: compact ? nil : .infinity)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel(title)
            .accessibilityHint("Opens calendar")

            Button {
                shift(by: 1)
            } label: {
                Image(systemName: "chevron.right")
                    .font(compact ? .subheadline.weight(.semibold) : .body.weight(.semibold))
                    .frame(width: compact ? 28 : 44, height: compact ? 32 : 44)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("Next day")
        }
        .foregroundStyle(Color.capy.textPrimary)
        .padding(.horizontal, compact ? 4 : 4)
        .background {
            if !compact {
                Capsule().fill(Color.capy.surfaceElevated.opacity(0.92))
            }
        }
        .sheet(isPresented: $showCalendar) {
            NavigationStack {
                DatePicker(
                    "Day",
                    selection: Binding(
                        get: { selectedDay },
                        set: { selectedDay = calendar.startOfDay(for: $0) }
                    ),
                    displayedComponents: .date
                )
                .datePickerStyle(.graphical)
                .environment(\.calendar, calendar)
                .padding(.horizontal, 8)
                .navigationTitle("Select day")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Done") { showCalendar = false }
                            .fontWeight(.semibold)
                            .foregroundStyle(Color.capy.accent)
                    }
                    ToolbarItem(placement: .topBarLeading) {
                        if !calendar.isDateInToday(selectedDay) {
                            Button("Today") {
                                selectedDay = calendar.startOfDay(for: .now)
                                showCalendar = false
                            }
                        }
                    }
                }
            }
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
    }

    private func shift(by days: Int) {
        guard let next = calendar.date(byAdding: .day, value: days, to: selectedDay) else { return }
        selectedDay = calendar.startOfDay(for: next)
    }
}
