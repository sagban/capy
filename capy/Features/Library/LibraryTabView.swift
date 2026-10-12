import SwiftUI
import SwiftData

struct LibraryTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var items: [LibraryItem]

    @State private var kindFilter: LibraryKind = .meal
    @State private var showEditor = false

    private var aiItems: [LibraryItem] {
        items.filter { $0.kind == kindFilter && $0.origin == .aiGenerated }
    }

    private var userItems: [LibraryItem] {
        items.filter { $0.kind == kindFilter && $0.origin == .user }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                List {
                    Section {
                        Picker("Kind", selection: $kindFilter) {
                            ForEach(LibraryKind.allCases) { kind in
                                Text(kind.title).tag(kind)
                            }
                        }
                        .pickerStyle(.segmented)
                    }

                    Section("AI-generated") {
                        if aiItems.isEmpty {
                            Text("none yet")
                                .foregroundStyle(Color.capy.textSecondary)
                        } else {
                            ForEach(aiItems) { item in
                                libraryRow(item)
                            }
                            .onDelete { delete(aiItems, at: $0) }
                        }
                    }

                    Section("Yours") {
                        if userItems.isEmpty {
                            Text("add a custom \(kindFilter.title.lowercased().dropLast())")
                                .foregroundStyle(Color.capy.textSecondary)
                        } else {
                            ForEach(userItems) { item in
                                libraryRow(item)
                            }
                            .onDelete { delete(userItems, at: $0) }
                        }
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Library")
            .toolbar {
                SettingsToolbarButton()
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showEditor = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("Add library item")
                }
            }
            .sheet(isPresented: $showEditor) {
                LibraryEditorSheet(defaultKind: kindFilter)
                    .presentationDetents([.medium, .large])
            }
        }
    }

    private func libraryRow(_ item: LibraryItem) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(item.name)
                    .font(.headline)
                if item.origin == .aiGenerated {
                    Text("AI")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.capy.accentSoft, in: Capsule())
                }
            }
            Text("\(Int(item.calories)) cal · P \(Int(item.proteinG)) · C \(Int(item.carbsG)) · F \(Int(item.fatG))")
                .font(.subheadline)
                .foregroundStyle(Color.capy.textSecondary)
            if !item.detail.isEmpty {
                Text(item.detail)
                    .font(.caption)
                    .foregroundStyle(Color.capy.textSecondary)
            }
        }
    }

    private func delete(_ source: [LibraryItem], at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(source[index])
        }
    }
}

struct LibraryEditorSheet: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss

    let defaultKind: LibraryKind

    @State private var name = ""
    @State private var kind: LibraryKind
    @State private var origin: LibraryOrigin = .user
    @State private var detail = ""
    @State private var calories = 400.0
    @State private var protein = 30.0
    @State private var carbs = 40.0
    @State private var fat = 15.0

    init(defaultKind: LibraryKind) {
        self.defaultKind = defaultKind
        _kind = State(initialValue: defaultKind)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Item") {
                    TextField("Name", text: $name)
                    Picker("Kind", selection: $kind) {
                        ForEach(LibraryKind.allCases) { Text($0.title).tag($0) }
                    }
                    Picker("Origin", selection: $origin) {
                        Text(LibraryOrigin.user.title).tag(LibraryOrigin.user)
                        Text(LibraryOrigin.aiGenerated.title).tag(LibraryOrigin.aiGenerated)
                    }
                    TextField("Notes", text: $detail)
                }
                Section("Macros (per serving)") {
                    LabeledContent("Calories") {
                        TextField("cal", value: $calories, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Protein") {
                        TextField("g", value: $protein, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Carbs") {
                        TextField("g", value: $carbs, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Fat") {
                        TextField("g", value: $fat, format: .number).keyboardType(.decimalPad).multilineTextAlignment(.trailing)
                    }
                }
            }
            .navigationTitle("Add to library")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                        .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        .fontWeight(.semibold)
                }
            }
        }
    }

    private func save() {
        modelContext.insert(
            LibraryItem(
                name: name.trimmingCharacters(in: .whitespacesAndNewlines),
                kind: kind,
                origin: origin,
                detail: detail,
                calories: calories,
                proteinG: protein,
                carbsG: carbs,
                fatG: fat
            )
        )
        dismiss()
    }
}
