import SwiftUI
import SwiftData

struct MealConfirmationSheet: View {
    @Binding var lines: [ConfirmLine]
    @Binding var mealSlot: String
    var correctionOp: String? = nil
    let onConfirm: () -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    private var enabledMealTypes: [MealType] {
        mealTypes.filter(\.isEnabled)
    }

    private var isCorrection: Bool { lines.contains { $0.entryId != nil } || correctionOp == "remove" }
    private var isRemoval: Bool { correctionOp == "remove" }
    private var totals: MacroTotals { ConfirmMath.totals(lines) }

    var body: some View {
        NavigationStack {
            Form {
                if isRemoval {
                    Section("Remove") {
                        Text(lines.first?.name ?? "This item")
                    }
                } else {
                    Section("Meal") {
                        if !enabledMealTypes.isEmpty && !isCorrection {
                            Picker("Meal type", selection: $mealSlot) {
                                ForEach(enabledMealTypes) { type in
                                    Text(type.name).tag(type.name)
                                }
                            }
                        }
                        ForEach($lines) { $line in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(ReadableFoodName.display(line.name))
                                if let portion = line.portionLabel, !portion.isEmpty {
                                    Text(portion)
                                        .font(.caption)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                                sourceBadge(line)
                                Stepper(value: $line.grams, in: 5...2000, step: 5) {
                                    Text("\(Int(line.grams)) g")
                                }
                                if let prior = line.priorGrams {
                                    Text("\(Int(prior)) g → \(Int(line.grams)) g")
                                        .font(.caption)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                            }
                        }
                    }
                    Section("Macros") {
                        macroRow("Calories", Int(totals.calories.rounded()))
                        macroRow("Protein", Int(totals.proteinG.rounded()), suffix: " g")
                        macroRow("Carbs", Int(totals.carbsG.rounded()), suffix: " g")
                        macroRow("Fat", Int(totals.fatG.rounded()), suffix: " g")
                    }
                }
            }
            .navigationTitle(isRemoval ? "Remove" : (isCorrection ? "Correct" : "Confirm"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isRemoval ? "Remove" : (isCorrection ? "Update" : "Log it")) {
                        onConfirm()
                        dismiss()
                    }
                    .disabled(!isCorrection && mealSlot.isEmpty && !enabledMealTypes.isEmpty)
                    .fontWeight(.semibold)
                }
            }
            .onAppear {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
                if mealSlot.isEmpty {
                    mealSlot = MealTypeCatalog.suggestedName(from: enabledMealTypes) ?? enabledMealTypes.first?.name ?? ""
                }
            }
        }
    }

    @ViewBuilder
    private func sourceBadge(_ line: ConfirmLine) -> some View {
        if let title = SourceBadge.title(for: line.source) {
            if line.source == "web", let raw = line.citationUrl, let url = URL(string: raw) {
                Link(title, destination: url)
                    .font(.caption)
            } else {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color.capy.warning)
            }
        }
    }

    private func macroRow(_ label: String, _ value: Int, suffix: String = "") -> some View {
        LabeledContent(label) {
            Text("\(value)\(suffix)")
                .contentTransition(.numericText())
                .animation(.easeOut(duration: 0.2), value: value)
        }
    }
}
