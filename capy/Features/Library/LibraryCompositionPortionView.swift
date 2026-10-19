import SwiftUI

/// Portion editor (amount + unit) before confirming into a recipe/meal.
struct LibraryCompositionPortionView: View {
    @Environment(\.unitPreferences) private var units

    @State var draft: CompositionPickDraft
    @State private var portionUnit: PortionUnit = .serving
    let onAdd: (LibraryIngredientLine) -> Void

    private var portionBinding: Binding<Double> {
        Binding(
            get: {
                portionUnit.amount(fromGrams: draft.grams, servingGrams: draft.servingGrams)
            },
            set: {
                draft.grams = portionUnit.grams(
                    fromAmount: max($0, 0),
                    servingGrams: draft.servingGrams
                )
            }
        )
    }

    private var isEditing: Bool { draft.existingLineId != nil }

    var body: some View {
        Form {
            Section {
                Text(draft.name)
                    .font(.title3.weight(.bold))
                    .foregroundStyle(Color.capy.textPrimary)
                    .textInputAutocapitalization(.words)
                if !draft.detail.isEmpty, draft.detail != draft.name {
                    Text(draft.detail)
                        .font(.subheadline)
                        .foregroundStyle(Color.capy.textSecondary)
                }
                FoodMacroBadgeRow(
                    calories: draft.macros.calories,
                    carbsG: draft.macros.carbsG,
                    fatG: draft.macros.fatG,
                    proteinG: draft.macros.proteinG
                )
            }

            Section {
                HStack(spacing: 10) {
                    Text("Portion")
                    Spacer(minLength: 8)
                    TextField(
                        "0",
                        value: portionBinding,
                        format: .number.precision(.fractionLength(portionUnit.fractionDigits))
                    )
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                    .frame(width: 72)
                    Picker("Unit", selection: $portionUnit) {
                        ForEach(PortionUnit.allCases) { unit in
                            Text(unit.shortLabel).tag(unit)
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.menu)
                    .onChange(of: portionUnit) { oldUnit, newUnit in
                        guard oldUnit != newUnit else { return }
                        let amount = oldUnit.amount(
                            fromGrams: draft.grams,
                            servingGrams: draft.servingGrams
                        )
                        draft.grams = newUnit.grams(
                            fromAmount: amount,
                            servingGrams: draft.servingGrams
                        )
                    }
                }
            } footer: {
                if portionUnit == .serving {
                    Text("1 serving = \(units.formattedFoodMass(draft.servingGrams, decimals: 0)).")
                }
            }
        }
        .navigationTitle(isEditing ? "Edit portion" : "Set portion")
        .navigationBarTitleDisplayMode(.inline)
        .scrollDismissesKeyboard(.interactively)
        .keyboardDoneToolbar()
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button(isEditing ? "Save" : "Add") {
                    Keyboard.dismiss()
                    onAdd(draft.asIngredientLine())
                }
                .fontWeight(.semibold)
                .disabled(draft.grams <= 0)
            }
        }
    }
}
