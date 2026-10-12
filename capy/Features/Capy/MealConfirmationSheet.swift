import SwiftUI
import SwiftData

struct MealConfirmationSheet: View {
    let name: String
    @Binding var grams: Double
    var baseGrams: Double = 100
    @Binding var mealSlot: String
    /// Macro totals for `baseGrams` (from Swift Core × catalog per100g).
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
    let onConfirm: () -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    private var scale: Double {
        guard baseGrams > 0 else { return 1 }
        return grams / baseGrams
    }

    private var enabledMealTypes: [MealType] {
        mealTypes.filter(\.isEnabled)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Meal") {
                    Text(name)
                    if !enabledMealTypes.isEmpty {
                        Picker("Meal type", selection: $mealSlot) {
                            ForEach(enabledMealTypes) { type in
                                Text(type.name).tag(type.name)
                            }
                        }
                    }
                    Stepper(value: $grams, in: 50...800, step: 10) {
                        Text("\(Int(grams)) g")
                    }
                }
                Section("Macros (approx)") {
                    LabeledContent("Calories", value: "\(Int((calories * scale).rounded()))")
                    LabeledContent("Protein", value: "\(Int((protein * scale).rounded())) g")
                    LabeledContent("Carbs", value: "\(Int((carbs * scale).rounded())) g")
                    LabeledContent("Fat", value: "\(Int((fat * scale).rounded())) g")
                }
            }
            .navigationTitle("Confirm")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Log it") {
                        onConfirm()
                        dismiss()
                    }
                    .disabled(mealSlot.isEmpty && !enabledMealTypes.isEmpty)
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
}
