import SwiftUI
import SwiftData

struct LibraryTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var items: [LibraryItem]

    @State private var kindFilter: LibraryKind = .meal
    @State private var showEditor = false
    @State private var searchText = ""

    private var filteredItems: [LibraryItem] {
        let kindMatched = items.filter { $0.kind == kindFilter }
        let q = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return kindMatched }
        return kindMatched.filter {
            $0.name.lowercased().contains(q) || $0.detail.lowercased().contains(q)
        }
    }

    private var aiItems: [LibraryItem] {
        filteredItems.filter { $0.origin == .aiGenerated }
    }

    private var userItems: [LibraryItem] {
        filteredItems.filter { $0.origin == .user }
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
                            Text(searchText.isEmpty ? "none yet" : "no matches")
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
                            Text(
                                searchText.isEmpty
                                ? "add a custom \(kindFilter.title.lowercased().dropLast())"
                                : "no matches"
                            )
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
            .searchable(text: $searchText, prompt: "Search library")
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
            .scrollDismissesKeyboard(.interactively)
            .keyboardDoneToolbar()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Keyboard.dismiss()
                        save()
                    }
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
                origin: .user,
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
