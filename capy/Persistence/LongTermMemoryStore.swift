import Foundation
import SwiftData

enum LongTermMemoryStore {
    static let contextCap = 40

    static func allNotes(in context: ModelContext) -> [LongTermMemoryNote] {
        let descriptor = FetchDescriptor<LongTermMemoryNote>(
            sortBy: [SortDescriptor(\.updatedAt, order: .reverse)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }

    static func notesForContext(in context: ModelContext, limit: Int = contextCap) -> [LongTermMemoryNote] {
        Array(allNotes(in: context).prefix(limit))
    }

    @discardableResult
    static func add(text: String, source: LongTermMemorySource, in context: ModelContext) -> LongTermMemoryNote {
        let note = LongTermMemoryNote(text: text.trimmingCharacters(in: .whitespacesAndNewlines), source: source)
        context.insert(note)
        return note
    }

    static func update(id: String, text: String, in context: ModelContext) {
        guard let note = fetch(id: id, in: context) else { return }
        note.text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        note.updatedAt = .now
        note.source = .user
    }

    static func delete(id: String, in context: ModelContext) {
        guard let note = fetch(id: id, in: context) else { return }
        context.delete(note)
    }

    static func apply(proposals: [MemoryProposalDTO], in context: ModelContext) {
        for proposal in proposals {
            switch proposal.action {
            case .add:
                guard let text = proposal.text?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else {
                    continue
                }
                if let id = proposal.id {
                    if let existing = fetch(id: id, in: context) {
                        existing.text = text
                        existing.updatedAt = .now
                        existing.source = .agent
                    } else {
                        let note = LongTermMemoryNote(id: id, text: text, source: .agent)
                        context.insert(note)
                    }
                } else {
                    add(text: text, source: .agent, in: context)
                }
            case .update:
                guard let id = proposal.id, let text = proposal.text else { continue }
                if let note = fetch(id: id, in: context) {
                    note.text = text.trimmingCharacters(in: .whitespacesAndNewlines)
                    note.updatedAt = .now
                    note.source = .agent
                }
            case .delete:
                if let id = proposal.id {
                    delete(id: id, in: context)
                } else if let text = proposal.text?.lowercased() {
                    for note in allNotes(in: context) where note.text.lowercased().contains(text) {
                        context.delete(note)
                    }
                }
            }
        }
    }

    private static func fetch(id: String, in context: ModelContext) -> LongTermMemoryNote? {
        var descriptor = FetchDescriptor<LongTermMemoryNote>(predicate: #Predicate { $0.id == id })
        descriptor.fetchLimit = 1
        return try? context.fetch(descriptor).first
    }
}
