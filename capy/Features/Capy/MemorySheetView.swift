import SwiftUI
import SwiftData

struct MemorySheetView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LongTermMemoryNote.updatedAt, order: .reverse) private var notes: [LongTermMemoryNote]

    @State private var draft = ""
    @State private var editingId: String?
    @State private var editText = ""

    var body: some View {
        NavigationStack {
            List {
                if notes.isEmpty {
                    Section {
                        Text("Capy saves standing facts here — habits, constraints, and context that don’t fit food prefs.")
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                } else {
                    Section {
                        ForEach(notes, id: \.id) { note in
                            Button {
                                editingId = note.id
                                editText = note.text
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(note.text)
                                        .foregroundStyle(Color.capy.textPrimary)
                                        .multilineTextAlignment(.leading)
                                    Text(note.source == .agent ? "Saved by Capy" : "Added by you")
                                        .font(.caption2)
                                        .foregroundStyle(Color.capy.textSecondary)
                                }
                            }
                        }
                        .onDelete(perform: delete)
                    }
                }

                Section {
                    TextField("Add a memory…", text: $draft, axis: .vertical)
                        .lineLimit(2...4)
                    Button("Add") {
                        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard !text.isEmpty else { return }
                        LongTermMemoryStore.add(text: text, source: .user, in: modelContext)
                        draft = ""
                    }
                    .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .foregroundStyle(Color.capy.accent)
                } footer: {
                    Text("Food prefs & diets are in Settings.")
                }
            }
            .navigationTitle("Memory")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: Binding(
                get: { editingId != nil },
                set: { if !$0 { editingId = nil } }
            )) {
                NavigationStack {
                    Form {
                        TextField("Memory", text: $editText, axis: .vertical)
                            .lineLimit(3...8)
                    }
                    .navigationTitle("Edit memory")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { editingId = nil }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Save") {
                                if let id = editingId {
                                    LongTermMemoryStore.update(id: id, text: editText, in: modelContext)
                                }
                                editingId = nil
                            }
                            .disabled(editText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        }
                    }
                }
                .presentationDetents([.medium])
            }
        }
    }

    private func delete(at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(notes[index])
        }
    }
}
