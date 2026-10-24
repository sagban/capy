import SwiftUI

struct CapyConversationInfoView: View {
    var loadedMessageIds: Set<String>
    var onJump: (String) -> Void
    var onReset: () async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var showResetConfirm = false
    @State private var isResetting = false
    @State private var resetError: String?

    private var stars: StarredMessagesStore { .shared }

    var body: some View {
        NavigationStack {
            infoList
        }
    }

    private var infoList: some View {
        List {
            Section {
                VStack(spacing: 8) {
                    Image("CapyAvatar")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 84, height: 84)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Color.capy.accentSoft, lineWidth: 1.5))
                    Text("Capy")
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(Color.capy.textPrimary)
                    Text("Chat")
                        .font(.subheadline)
                        .foregroundStyle(Color.capy.textSecondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .listRowBackground(Color.clear)
            }
            Section {
                NavigationLink {
                    CapyMessageSearchView(loadedMessageIds: loadedMessageIds, onJump: onJump)
                } label: {
                    Label("Search", systemImage: "magnifyingglass")
                }
                NavigationLink {
                    CapyStarredMessagesView(loadedMessageIds: loadedMessageIds, onJump: onJump)
                } label: {
                    HStack {
                        Label("Starred messages", systemImage: "star")
                        Spacer()
                        if !stars.items.isEmpty {
                            Text("\(stars.items.count)")
                                .foregroundStyle(Color.capy.textSecondary)
                        }
                    }
                }
            }
            Section {
                Button(role: .destructive) {
                    showResetConfirm = true
                } label: {
                    if isResetting {
                        HStack {
                            ProgressView()
                            Text("Resetting…")
                        }
                    } else {
                        Label("Reset conversation", systemImage: "arrow.counterclockwise")
                    }
                }
                .disabled(isResetting)
            }
        }
        .navigationTitle("Capy")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Done") { dismiss() }
            }
        }
        .confirmationDialog(
            "Reset the conversation?",
            isPresented: $showResetConfirm,
            titleVisibility: .visible
        ) {
            Button("Reset", role: .destructive) {
                Task { await reset() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This deletes the messages in this chat, including starred ones.")
        }
        .alert(
            "Couldn’t reset the chat",
            isPresented: Binding(
                get: { resetError != nil },
                set: { if !$0 { resetError = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(resetError ?? "")
        }
    }

    private func reset() async {
        isResetting = true
        defer { isResetting = false }
        do {
            try await onReset()
        } catch {
            resetError = "The chat is still here. Try again."
            #if DEBUG
            print("[CapyConversationInfo] reset failed: \(error)")
            #endif
        }
    }
}

private struct CapyMessageSearchView: View {
    var loadedMessageIds: Set<String>
    var onJump: (String) -> Void

    @State private var query = ""
    @State private var hits: [ThreadMessageDTO] = []
    @State private var isSearching = false
    @State private var searched = false
    @State private var searchTask: Task<Void, Never>?
    @State private var searchGeneration = 0

    var body: some View {
        List {
            if isSearching {
                CapyInlineLoader(label: "Searching…")
            } else if searched, hits.isEmpty {
                Text("No messages match.")
                    .foregroundStyle(Color.capy.textSecondary)
            } else {
                ForEach(hits, id: \.messageId) { hit in
                    messageRow(
                        id: hit.messageId,
                        role: hit.role,
                        text: hit.text,
                        day: dayLabel(hit.createdAt)
                    )
                }
            }
        }
        .navigationTitle("Search")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: "Message")
        .onChange(of: query) { _, newValue in
            searchTask?.cancel()
            searchGeneration += 1
            let trimmed = newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            guard trimmed.count >= 2 else {
                hits = []
                searched = false
                isSearching = false
                return
            }
            let generation = searchGeneration
            searchTask = Task {
                try? await Task.sleep(for: .milliseconds(300))
                guard !Task.isCancelled else { return }
                await runSearch(trimmed, generation: generation)
            }
        }
    }

    private func runSearch(_ needle: String, generation: Int) async {
        isSearching = true
        defer {
            if generation == searchGeneration {
                isSearching = false
            }
        }
        var found: [ThreadMessageDTO] = []
        var cursor: String?
        for _ in 0..<8 {
            if Task.isCancelled || generation != searchGeneration { return }
            do {
                let page = try await CapyThreadService.fetchThread(limit: 50, cursor: cursor)
                for message in page.messages where message.text.localizedCaseInsensitiveContains(needle) {
                    found.append(message)
                }
                guard page.pageInfo.hasMore, let next = page.pageInfo.nextCursor, !next.isEmpty, next != cursor else {
                    break
                }
                cursor = next
            } catch {
                #if DEBUG
                print("[CapyMessageSearch] get_thread failed: \(error)")
                #endif
                break
            }
        }
        guard generation == searchGeneration else { return }
        hits = found
        searched = true
    }

    @ViewBuilder
    private func messageRow(id: String, role: String, text: String, day: String) -> some View {
        let loaded = loadedMessageIds.contains(id)
        Button {
            if loaded { onJump(id) }
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(roleTitle(role))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.capy.accent)
                    Spacer()
                    if !day.isEmpty {
                        Text(day)
                            .font(.caption)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
                Text(text)
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textPrimary)
                    .lineLimit(4)
                    .multilineTextAlignment(.leading)
            }
        }
        .buttonStyle(.plain)
    }
}

private struct CapyStarredMessagesView: View {
    var loadedMessageIds: Set<String>
    var onJump: (String) -> Void

    private var stars: StarredMessagesStore { .shared }

    var body: some View {
        List {
            if stars.items.isEmpty {
                Text("No starred messages.")
                    .foregroundStyle(Color.capy.textSecondary)
            } else {
                ForEach(stars.items) { item in
                    messageRow(item)
                }
            }
        }
        .navigationTitle("Starred")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func messageRow(_ item: StarredMessage) -> some View {
        let loaded = loadedMessageIds.contains(item.id)
        return Button {
            if loaded { onJump(item.id) }
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(roleTitle(item.role))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color.capy.accent)
                Text(item.text)
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textPrimary)
                    .lineLimit(4)
                    .multilineTextAlignment(.leading)
            }
        }
        .buttonStyle(.plain)
        .swipeActions {
            Button("Unstar", role: .destructive) {
                stars.toggle(id: item.id, role: item.role == "user" ? .user : .capy, text: item.text)
            }
        }
    }
}

private func roleTitle(_ role: String) -> String {
    role.lowercased() == "user" ? "You" : "Capy"
}

private func dayLabel(_ createdAt: String?) -> String {
    guard let createdAt, createdAt.count >= 10 else { return "" }
    return String(createdAt.prefix(10))
}
