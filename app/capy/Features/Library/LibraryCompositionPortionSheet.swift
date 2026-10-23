import SwiftUI

/// Edit an existing line’s portion in a sheet.
struct LibraryCompositionPortionSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var draft: CompositionPickDraft
    let onSave: (LibraryIngredientLine) -> Void

    init(line: LibraryIngredientLine, onSave: @escaping (LibraryIngredientLine) -> Void) {
        _draft = State(initialValue: .from(line: line))
        self.onSave = onSave
    }

    var body: some View {
        NavigationStack {
            LibraryCompositionPortionView(draft: draft) { line in
                onSave(line)
                dismiss()
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}
