import SwiftUI
import SwiftData

struct CapyTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]
    @Query private var entries: [MealEntry]
    @Query private var settings: [AppSettings]

    @State private var draft = ""
    @State private var messages: [ChatBubble] = [
        ChatBubble(role: .capy, text: "what did you have to eat?"),
    ]
    @State private var showConfirm = false
    @State private var pendingName = ""
    @State private var pendingCalories = 450.0
    @State private var pendingProtein = 30.0
    @State private var pendingCarbs = 40.0
    @State private var pendingFat = 15.0
    @State private var pendingGrams = 250.0
    @State private var pickIndex = 0
    @State private var abstained = false

    private let samplePicks = [
        SamplePick(name: "Chicken stir-fry", calories: 420, protein: 42, carbs: 18, fat: 18, reasons: ["fits with room", "no repeat from today"]),
        SamplePick(name: "Greek yogurt bowl", calories: 380, protein: 28, carbs: 42, fat: 12, reasons: ["fits budget", "uses a regular"]),
        SamplePick(name: "Dal + roti", calories: 460, protein: 22, carbs: 62, fat: 12, reasons: ["fits", "variety ok"]),
    ]

    private var todayKey: String { DayKey.make() }

    private var todayEntries: [MealEntry] {
        entries.filter { $0.dayKey == todayKey && $0.confirmed }
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
        todayEntries.reduce(.zero) { partial, entry in
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

    private var overTarget: Bool {
        eaten.calories > target.calories
    }

    private var currentPick: SamplePick {
        samplePicks[pickIndex % samplePicks.count]
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                VStack(spacing: 12) {
                    BudgetBarView(remaining: remaining, target: target, overTarget: overTarget)
                        .padding(.horizontal)

                    if abstained {
                        GlassPanel {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("nothing in your regulars fits cleanly")
                                    .font(.headline)
                                    .foregroundStyle(Color.capy.textPrimary)
                                Text("want a smaller snack instead, or log what you have?")
                                    .foregroundStyle(Color.capy.textSecondary)
                            }
                        }
                        .padding(.horizontal)
                    } else {
                        pickCard
                            .padding(.horizontal)
                    }

                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            ForEach(messages) { message in
                                HStack {
                                    if message.role == .user { Spacer(minLength: 40) }
                                    Text(message.text)
                                        .padding(12)
                                        .background(
                                            message.role == .capy
                                            ? Color.capy.accentSoft.opacity(0.7)
                                            : Color.capy.surfaceElevated.opacity(0.9),
                                            in: RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        )
                                        .foregroundStyle(Color.capy.textPrimary)
                                    if message.role == .capy { Spacer(minLength: 40) }
                                }
                            }
                        }
                        .padding(.horizontal)
                    }

                    talkBox
                        .padding(.horizontal)
                        .padding(.bottom, 8)
                }
            }
            .navigationTitle("Capy")
            .toolbar { SettingsToolbarButton() }
            .sheet(isPresented: $showConfirm) {
                MealConfirmationSheet(
                    name: pendingName,
                    grams: $pendingGrams,
                    calories: pendingCalories,
                    protein: pendingProtein,
                    carbs: pendingCarbs,
                    fat: pendingFat,
                    onConfirm: confirmPending
                )
                .presentationDetents([.medium])
            }
        }
    }

    private var pickCard: some View {
        GlassPanel {
            VStack(alignment: .leading, spacing: 12) {
                Text(currentPick.name)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Color.capy.textPrimary)
                Text("\(Int(currentPick.calories)) cal · P \(Int(currentPick.protein)) · C \(Int(currentPick.carbs)) · F \(Int(currentPick.fat))")
                    .foregroundStyle(Color.capy.textSecondary)
                HStack {
                    ForEach(currentPick.reasons, id: \.self) { reason in
                        Text(reason)
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.capy.accentSoft, in: Capsule())
                    }
                }
                HStack {
                    Button("Log it") { logPick() }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.capy.accent)
                    Button("Swap") { swapPick() }
                        .buttonStyle(.bordered)
                    Button("Not this") { abstained = true }
                        .buttonStyle(.bordered)
                }
            }
        }
    }

    private var talkBox: some View {
        HStack(spacing: 10) {
            TextField("tell Capy what you ate…", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .padding(12)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            Button {
                send()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(Color.capy.accent)
            }
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .accessibilityLabel("Send")
        }
    }

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        messages.append(ChatBubble(role: .user, text: text))
        draft = ""
        pendingName = text
        pendingCalories = 520
        pendingProtein = 35
        pendingCarbs = 48
        pendingFat = 18
        pendingGrams = 300
        showConfirm = true
        let level = settings.first?.assistanceLevel ?? .fullAssist
        if level == .quiet {
            messages.append(ChatBubble(role: .capy, text: "confirm portions when you’re ready."))
        } else {
            messages.append(ChatBubble(role: .capy, text: "got it — confirm the portions and I’ll bank it."))
        }
    }

    private func confirmPending() {
        let item = MealEntryItem(
            name: pendingName,
            grams: pendingGrams,
            calories: pendingCalories * (pendingGrams / 300),
            proteinG: pendingProtein * (pendingGrams / 300),
            carbsG: pendingCarbs * (pendingGrams / 300),
            fatG: pendingFat * (pendingGrams / 300)
        )
        let entry = MealEntry(
            dayKey: todayKey,
            originalUserText: pendingName,
            confirmed: true,
            items: [item]
        )
        modelContext.insert(entry)
        showConfirm = false
        abstained = false
        let left = MacroTotals.remaining(target: target, eaten: MacroTotals(
            calories: eaten.calories + item.calories,
            proteinG: eaten.proteinG + item.proteinG,
            carbsG: eaten.carbsG + item.carbsG,
            fatG: eaten.fatG + item.fatG
        ))
        let level = settings.first?.assistanceLevel ?? .fullAssist
        if level == .quiet {
            messages.append(ChatBubble(role: .capy, text: "logged. \(Int(left.calories)) left."))
        } else {
            messages.append(ChatBubble(
                role: .capy,
                text: "logged — ~\(Int(item.calories)) cal banked. \(Int(left.calories)) cal left. dinner pick still fits."
            ))
        }
    }

    private func logPick() {
        pendingName = currentPick.name
        pendingCalories = currentPick.calories
        pendingProtein = currentPick.protein
        pendingCarbs = currentPick.carbs
        pendingFat = currentPick.fat
        pendingGrams = 300
        showConfirm = true
    }

    private func swapPick() {
        abstained = false
        pickIndex += 1
        messages.append(ChatBubble(role: .capy, text: "swapped — try \(currentPick.name)."))
    }
}

struct ChatBubble: Identifiable {
    enum Role { case capy, user }
    let id = UUID()
    let role: Role
    let text: String
}

struct SamplePick {
    let name: String
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
    let reasons: [String]
}
