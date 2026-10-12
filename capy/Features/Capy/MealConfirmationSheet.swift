import SwiftUI

struct MealConfirmationSheet: View {
    let name: String
    @Binding var grams: Double
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
    let onConfirm: () -> Void

    @Environment(\.dismiss) private var dismiss

    private var scale: Double { grams / 300 }

    var body: some View {
        NavigationStack {
            Form {
                Section("Meal") {
                    Text(name)
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
                    .fontWeight(.semibold)
                }
            }
        }
    }
}
