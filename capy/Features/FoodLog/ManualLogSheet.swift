import SwiftUI
import SwiftData

struct ManualLogSheet: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var library: [LibraryItem]

    let dayKey: String

    @State private var query = ""
    @State private var name = ""
    @State private var grams = 200.0
    @State private var calories = 300.0
    @State private var protein = 20.0
    @State private var carbs = 30.0
    @State private var fat = 10.0

    private var filtered: [LibraryItem] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return Array(library.prefix(8)) }
        return library.filter { $0.name.lowercased().contains(q) }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Search library") {
                    TextField("Search meals, recipes, foods", text: $query)
                    ForEach(filtered) { item in
                        Button {
                            name = item.name
                            calories = item.calories
                            protein = item.proteinG
                            carbs = item.carbsG
                            fat = item.fatG
                        } label: {
                            VStack(alignment: .leading) {
                                Text(item.name)
                                Text(item.origin.title)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                Section("Entry") {
                    TextField("Name", text: $name)
                    Stepper("Grams: \(Int(grams))", value: $grams, in: 20...1000, step: 10)
                    LabeledContent("Calories") {
                        TextField("cal", value: $calories, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Protein") {
                        TextField("g", value: $protein, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Carbs") {
                        TextField("g", value: $carbs, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Fat") {
                        TextField("g", value: $fat, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                }
            }
            .navigationTitle("Log food")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Log it") { save() }
                        .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        .fontWeight(.semibold)
                }
            }
        }
    }

    private func save() {
        let item = MealEntryItem(
            name: name,
            grams: grams,
            calories: calories,
            proteinG: protein,
            carbsG: carbs,
            fatG: fat
        )
        modelContext.insert(
            MealEntry(
                dayKey: dayKey,
                originalUserText: name,
                confirmed: true,
                items: [item]
            )
        )
        dismiss()
    }
}
