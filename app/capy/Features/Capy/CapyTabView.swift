import SwiftUI
import SwiftData
import FirebaseAuth

struct CapyTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.scenePhase) private var scenePhase
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]
    @Query private var entries: [MealEntry]
    @Query private var settings: [AppSettings]
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]
    @Query(sort: \LibraryItem.createdAt, order: .reverse) private var libraryItems: [LibraryItem]

    @State private var draft = ""
    @State private var messages: [ChatBubble] = []
    @State private var showConfirm = false
    @State private var showManualLog = false
    @State private var pendingLines: [ConfirmLine] = []
    @State private var pendingMealSlot = ""
    @State private var pendingCorrectionOp: String?
    @State private var showDeleteConfirm = false
    @State private var pendingDelete: PendingDeleteContext?
    @State private var isSending = false
    @State private var isLoadingThread = false
    @State private var lastUtterance = ""
    @State private var speech = SpeechInputController()
    @FocusState private var talkFocused: Bool
    @State private var showMemory = false
    @State private var didLoadThread = false
    @State private var historyCursor: String?
    @State private var hasMoreHistory = false
    @State private var isLoadingOlder = false
    @State private var stickToBottom = true
    @AppStorage("capy.lastConversationDayKey") private var lastConversationDayKey = ""
    @AppStorage("capy.eveningCheckInDayKey") private var eveningCheckInDayKey = ""

    private var todayKey: String { DayKey.make() }

    private var todayEntries: [MealEntry] {
        entries.filter { $0.dayKey == todayKey && $0.confirmed }
    }

    private var target: MacroTotals {
        let t = targets.first
        return MacroTotals(
            calories: t?.calories ?? 2000,
            proteinG: t?.proteinG ?? 140,
            carbsG: t?.carbsG ?? 200,
            fatG: t?.fatG ?? 65
        )
    }

    private var eaten: MacroTotals {
        todayEntries.reduce(.zero) { partial, entry in
            MacroTotals(
                calories: partial.calories + entry.calories,
                proteinG: partial.proteinG + entry.proteinG,
                carbsG: partial.carbsG + entry.carbsG,
                fatG: partial.fatG + entry.fatG
            )
        }
    }

    private var remaining: MacroTotals {
        MacroTotals.remaining(target: target, eaten: eaten)
    }

    private var canSend: Bool {
        !isSending && !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()

                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            if hasMoreHistory || isLoadingOlder {
                                Group {
                                    if isLoadingOlder {
                                        CapyInlineLoader(label: "Loading earlier…")
                                    } else {
                                        Text("Load earlier")
                                            .font(.caption)
                                            .foregroundStyle(Color.capy.textSecondary)
                                            .frame(maxWidth: .infinity)
                                            .padding(.vertical, 8)
                                    }
                                }
                                .onAppear { Task { await loadOlderMessages() } }
                            }
                            if messages.isEmpty, !isLoadingThread { starterPrompts }
                            ForEach(messages) { message in
                                chatBubble(message)
                                    .id(message.id)
                                    .capyAppear()
                            }
                            if isSending {
                                HStack {
                                    CapyTypingIndicator()
                                    Spacer(minLength: 48)
                                }
                                .transition(.opacity.combined(with: .move(edge: .bottom)))
                            }
                        }
                        .padding(.horizontal)
                        .padding(.top, 12)
                        .padding(.bottom, 16)
                        // Tall hit target so taps in empty chat area dismiss the keyboard.
                        // simultaneousGesture + TapGesture: scroll/drag must not count as a tap.
                        .frame(maxWidth: .infinity, minHeight: 420, alignment: .topLeading)
                        .contentShape(Rectangle())
                        .simultaneousGesture(
                            TapGesture().onEnded { dismissTalkKeyboard() }
                        )
                    }
                    // Don't hide keyboard just because the user scrolled the thread.
                    .scrollDismissesKeyboard(.never)
                    .onChange(of: messages.count) { _, _ in
                        guard stickToBottom, let last = messages.last?.id else { return }
                        withAnimation(.easeOut(duration: 0.22)) {
                            proxy.scrollTo(last, anchor: .bottom)
                        }
                    }
                    .onChange(of: isSending) { _, sending in
                        guard sending, stickToBottom else { return }
                        withAnimation(.easeOut(duration: 0.22)) {
                            proxy.scrollTo(messages.last?.id, anchor: .bottom)
                        }
                    }
                }

                if isLoadingThread {
                    CapyThreadLoadingOverlay()
                }
            }
            .animation(.easeInOut(duration: 0.2), value: isLoadingThread)
            .animation(.spring(response: 0.35, dampingFraction: 0.86), value: isSending)
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: 6) {
                    if let error = speech.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(Color.capy.warning)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 20)
                    }
                    talkBox
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 10)
                }
                .background(
                    Color.capy.background
                        .shadow(color: Color.black.opacity(0.06), radius: 10, y: -4)
                        .ignoresSafeArea(edges: .bottom)
                )
            }
            .toolbarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Image("CapyAvatar")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 36, height: 36)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Color.capy.accentSoft, lineWidth: 1.5))
                        .accessibilityLabel("Capy")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showMemory = true
                    } label: {
                        Image(systemName: "brain.head.profile")
                    }
                    .accessibilityLabel("Memory")
                }
                SettingsToolbarButton()
            }
            // No keyboard Done toolbar — it collides with the in-composer Send;
            // return key is .send and taps outside dismiss.
            .sheet(isPresented: $showConfirm) {
                confirmSheet
                    .presentationDetents([.medium, .large])
            }
            .sheet(isPresented: $showManualLog) {
                ManualLogSheet(dayKey: todayKey, initialMealSlot: pendingMealSlot.isEmpty ? nil : pendingMealSlot)
            }
            .sheet(isPresented: $showMemory) {
                MemorySheetView()
            }
            .task {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
                await loadThreadFromServerIfNeeded()
                handleDayRolloverIfNeeded()
                maybeEveningCheckIn()
            }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { maybeEveningCheckIn() }
            }
            .onChange(of: speech.transcript) { _, newValue in
                guard speech.isRecording, !newValue.isEmpty else { return }
                draft = newValue
            }
            .onChange(of: speech.isRecording) { wasRecording, isRecording in
                if wasRecording && !isRecording {
                    let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !text.isEmpty { dismissTalkKeyboard() }
                }
            }
            .onDisappear {
                speech.stop()
            }
            .confirmationDialog(
                "Delete this entry?",
                isPresented: $showDeleteConfirm,
                titleVisibility: .visible
            ) {
                Button("Delete", role: .destructive) {
                    confirmDeletePending()
                }
                Button("Cancel", role: .cancel) {
                    cancelDeletePending()
                }
            } message: {
                if let pendingDelete {
                    Text(pendingDelete.label)
                }
            }
        }
    }

    @ViewBuilder
    private var confirmSheet: some View {
        MealConfirmationSheet(
            lines: $pendingLines,
            mealSlot: $pendingMealSlot,
            correctionOp: pendingCorrectionOp,
            onConfirm: { confirmPending() }
        )
    }

    private static let starters = [
        "What should I eat?",
        "Same breakfast as yesterday",
        "I had 4 eggs and 2 slices of sourdough",
    ]

    private var starterPrompts: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Log what you ate, or ask what fits your day.")
                .font(.subheadline)
                .foregroundStyle(Color.capy.textSecondary)
            ForEach(Array(Self.starters.enumerated()), id: \.element) { index, prompt in
                Button {
                    draft = prompt
                    send()
                } label: {
                    Text(prompt)
                        .font(.subheadline)
                        .foregroundStyle(Color.capy.textPrimary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            Color.capy.surfaceElevated,
                            in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                        )
                }
                .buttonStyle(.plain)
                .capyAppear()
                .animation(.spring(response: 0.4, dampingFraction: 0.86).delay(Double(index) * 0.05), value: messages.isEmpty)
            }
        }
        .padding(.top, 8)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }

    private func chatBubble(_ message: ChatBubble) -> some View {
        HStack {
            if message.role == .user { Spacer(minLength: 48) }
            VStack(alignment: .leading, spacing: 8) {
                if !message.text.isEmpty {
                    Text(message.text)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            message.role == .user ? Color.capy.accent : Color.capy.surfaceElevated,
                            in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                        )
                        .foregroundStyle(message.role == .user ? Color.white : Color.capy.textPrimary)
                }
                if message.role == .error {
                    Button("Retry") { retryLast() }
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Color.capy.accent)
                }
                if message.manualLog {
                    Button("Manual Log") { showManualLog = true }
                        .font(.subheadline.weight(.semibold))
                }
            }
            if message.role != .user { Spacer(minLength: 48) }
        }
    }

    private var talkBox: some View {
        HStack(spacing: 8) {
            TextField("Message Capy…", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused($talkFocused)
                .submitLabel(.send)
                .foregroundStyle(Color.capy.textPrimary)
                .onSubmit {
                    if canSend { send() }
                }

            if canSend {
                Button {
                    send()
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.capy.accent)
                        .symbolEffect(.bounce, value: isSending)
                }
                .accessibilityLabel("Send")
                .transition(.scale.combined(with: .opacity))
            } else {
                Button {
                    dismissTalkKeyboard()
                    speech.toggle()
                } label: {
                    Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.fill")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(speech.isRecording ? Color.capy.budgetCalories : Color.capy.textPrimary)
                        .frame(width: 32, height: 32)
                        .contentTransition(.symbolEffect(.replace))
                        .capyRecordingPulse(speech.isRecording)
                }
                .accessibilityLabel(speech.isRecording ? "Stop listening" : "Speak to Capy")
                .transition(.scale.combined(with: .opacity))
            }
        }
        .animation(.spring(response: 0.32, dampingFraction: 0.82), value: canSend)
        .animation(.easeInOut(duration: 0.2), value: speech.isRecording)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.capy.surfaceElevated, in: Capsule())
        .overlay(
            Capsule()
                .stroke(
                    speech.isRecording
                    ? Color.capy.budgetCalories.opacity(0.75)
                    : Color.capy.textSecondary.opacity(0.18),
                    lineWidth: speech.isRecording ? 1.5 : 1
                )
        )
        .shadow(
            color: speech.isRecording
                ? Color.capy.budgetCalories.opacity(0.22)
                : Color.black.opacity(0.08),
            radius: speech.isRecording ? 12 : 8,
            y: 2
        )
    }

    @MainActor
    private func loadThreadFromServerIfNeeded() async {
        guard !didLoadThread else { return }
        didLoadThread = true
        guard Auth.auth().currentUser != nil else { return }
        isLoadingThread = true
        defer { isLoadingThread = false }
        do {
            let page = try await CapyThreadService.fetchThread()
            withAnimation(.easeOut(duration: 0.25)) {
                applyThreadPage(page, replacing: true)
            }
        } catch {
            #if DEBUG
            print("[CapyTabView] get_thread failed: \(error)")
            #endif
        }
    }

    private func stampManualLogBubble(reply: String) {
        if let index = messages.lastIndex(where: { $0.role == .capy }) {
            let last = messages[index]
            messages[index] = ChatBubble(
                serverMessageId: last.serverMessageId,
                role: .capy,
                text: last.text.isEmpty ? reply : last.text,
                manualLog: true
            )
        } else {
            messages.append(ChatBubble(role: .capy, text: reply, manualLog: true))
        }
    }

    @MainActor
    private func loadOlderMessages() async {
        guard hasMoreHistory, !isLoadingOlder, let cursor = historyCursor else { return }
        isLoadingOlder = true
        defer { isLoadingOlder = false }
        do {
            let page = try await CapyThreadService.fetchThread(cursor: cursor)
            prependThreadPage(page)
        } catch {
            #if DEBUG
            print("[CapyTabView] load older failed: \(error)")
            #endif
        }
    }

    private func applyThreadPage(_ page: GetThreadResponseDTO, replacing: Bool) {
        let bubbles = CapyThreadService.chatBubbles(from: page.messages)
        if replacing {
            messages = bubbles
            stickToBottom = true
        } else if !bubbles.isEmpty {
            messages = bubbles
        }
        historyCursor = page.pageInfo.nextCursor
        hasMoreHistory = page.pageInfo.hasMore
    }

    private func prependThreadPage(_ page: GetThreadResponseDTO) {
        let older = CapyThreadService.chatBubbles(from: page.messages)
        guard !older.isEmpty else {
            historyCursor = page.pageInfo.nextCursor
            hasMoreHistory = page.pageInfo.hasMore
            return
        }
        stickToBottom = false
        var seen = Set(messages.map(\.serverMessageId))
        let fresh = older.filter { seen.insert($0.serverMessageId).inserted }
        messages = fresh + messages
        historyCursor = page.pageInfo.nextCursor
        hasMoreHistory = page.pageInfo.hasMore
    }

    private func applyInterpretThread(_ response: InterpretMealResponseDTO) {
        if let pageMessages = response.messages, !pageMessages.isEmpty {
            let page = GetThreadResponseDTO(
                conversation: response.conversation ?? ConversationContextDTO(),
                messages: pageMessages,
                pageInfo: response.pageInfo ?? ThreadPageInfoDTO()
            )
            applyThreadPage(page, replacing: true)
            return
        }
        if let conversation = response.conversation, !conversation.recentTurns.isEmpty {
            let bubbles = conversation.recentTurns.compactMap { turn -> ChatBubble? in
                let role: ChatBubble.Role = turn.role.lowercased() == "user" ? .user : .capy
                return ChatBubble(role: role, text: turn.text)
            }
            if !bubbles.isEmpty {
                messages = bubbles
                stickToBottom = true
            }
        }
    }

    private func handleDayRolloverIfNeeded() {
        let today = todayKey
        if !lastConversationDayKey.isEmpty, lastConversationDayKey != today {
            let priorCount = entries.filter { $0.dayKey == lastConversationDayKey && $0.confirmed }.count
            Task {
                try? await CapyThreadService.noteDayRollover(
                    previousDayKey: lastConversationDayKey,
                    mealCount: priorCount
                )
            }
        }
        lastConversationDayKey = today
    }

    /// Unprompted evening check-in (Guided / Full Assist only). Quiet never speaks first.
    private func maybeEveningCheckIn() {
        let level = settings.first?.assistanceLevel ?? .fullAssist
        guard DialPolicy.allowsEveningCheckIn(level) else { return }
        guard DialPolicy.allowsUnpromptedMessages(level) else { return }
        guard eveningCheckInDayKey != todayKey else { return }

        let hour = settings.first?.guidedCheckInHour ?? 18
        let minute = settings.first?.guidedCheckInMinute ?? 0
        let now = Calendar.current.dateComponents([.hour, .minute], from: .now)
        let nowMinutes = (now.hour ?? 0) * 60 + (now.minute ?? 0)
        let gate = hour * 60 + minute
        guard nowMinutes >= gate else { return }

        let left = Int(remaining.calories)
        let text = left > 0
            ? "anything left to log? \(left) cal left."
            : "day’s budget is used — log a correction if something changed."
        messages.append(ChatBubble(role: .capy, text: text))
        Task { try? await CapyThreadService.appendAssistant(text) }
        eveningCheckInDayKey = todayKey
    }

    private func dismissTalkKeyboard() {
        talkFocused = false
        Keyboard.dismiss()
    }

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }
        speech.stop()
        dismissTalkKeyboard()
        stickToBottom = true
        draft = ""
        lastUtterance = text
        withAnimation(.spring(response: 0.35, dampingFraction: 0.86)) {
            messages.append(ChatBubble(role: .user, text: text))
            isSending = true
        }
        Task { await interpret(utterance: text) }
    }

    private func retryLast() {
        guard !isSending else { return }
        withAnimation(.spring(response: 0.35, dampingFraction: 0.86)) {
            messages.removeAll { $0.role == .error }
            isSending = true
        }
        Task { await interpret(utterance: lastUtterance) }
    }

    @MainActor
    private func interpret(utterance: String) async {
        defer {
            withAnimation(.easeOut(duration: 0.2)) {
                isSending = false
            }
        }
        await UserSyncService.shared.flushPending()
        let request = InterpretMealRequestDTO.serverContext(
            utterance: utterance,
            dayKey: todayKey,
            libraryContext: InterpretMealRequestDTO.librarySnapshot(from: libraryItems)
        )
        do {
            let response = try await AgentClient.shared.interpretMeal(request)
            if response.warnings.contains("agent_unavailable") {
                messages.append(ChatBubble(role: .error, text: ""))
                return
            }
            if let proposals = response.memoryProposals, !proposals.isEmpty {
                LongTermMemoryStore.apply(proposals: proposals, in: modelContext)
                UserSyncService.shared.scheduleProfileSync(in: modelContext)
            }
            let reply = response.assistantMessage.trimmingCharacters(in: .whitespacesAndNewlines)
            let manual = response.pendingAction?.payload.manualLog == true
            let noted = !(response.memoryProposals ?? []).isEmpty
            let suggested = !(response.suggestionOptions ?? []).isEmpty
            let showed = !reply.isEmpty || manual || response.pendingAction != nil || noted || suggested
            applyInterpretThread(response)
            if manual {
                stampManualLogBubble(reply: reply)
            }
            if response.messages == nil, response.conversation == nil, !reply.isEmpty || manual {
                messages.append(
                    ChatBubble(
                        role: .capy,
                        text: reply,
                        manualLog: manual
                    )
                )
            }
            handleStructuredResponse(response)
            if !showed {
                messages.append(ChatBubble(role: .error, text: ""))
            }
        } catch {
            messages.append(ChatBubble(role: .error, text: ""))
        }
    }

    private func handleStructuredResponse(_ response: InterpretMealResponseDTO) {
        pendingCorrectionOp = nil
        pendingDelete = nil
        guard let pending = response.pendingAction else { return }
        switch pending.type {
        case .confirmLog:
            let lines = confirmLines(from: pending.payload.resolvedItems)
            guard !lines.isEmpty else { return }
            pendingLines = lines
            pendingMealSlot = MealTypeCatalog.suggestedName(from: mealTypes.filter(\.isEnabled)) ?? ""
            showConfirm = true
        case .confirmCorrection:
            pendingCorrectionOp = pending.payload.correctionOp
            pendingLines = correctionLines(from: pending)
            showConfirm = !pendingLines.isEmpty || pendingCorrectionOp == "remove"
        case .confirmDelete:
            guard
                let entryId = pending.payload.entryId?.trimmingCharacters(in: .whitespacesAndNewlines),
                !entryId.isEmpty,
                let dayKey = pending.payload.dayKey?.trimmingCharacters(in: .whitespacesAndNewlines),
                !dayKey.isEmpty
            else { return }
            let reason = (pending.payload.reason ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            pendingDelete = PendingDeleteContext(
                entryId: entryId,
                dayKey: dayKey,
                label: reason.isEmpty ? "This meal" : reason
            )
            showDeleteConfirm = true
        case .clarifyFood, .clarifyPortion:
            break
        }
    }

    private func confirmLines(from items: [ResolvedItemDTO]) -> [ConfirmLine] {
        var seen = Set<String>()
        var lines: [ConfirmLine] = []
        for (index, item) in items.enumerated() {
            guard item.grams > 0 else { continue }
            let key = "\(item.foodId)|\(item.grams)"
            guard seen.insert(key).inserted else { continue }
            lines.append(
                ConfirmLine(
                    id: "\(index)-\(item.foodId)",
                    name: item.displayName,
                    foodId: item.foodId,
                    grams: item.grams,
                    per100g: item.per100g,
                    source: item.source,
                    citationUrl: item.citationUrl,
                    portionLabel: item.portionLabel,
                    family: item.family ?? "",
                    entryId: item.entryId,
                    itemIndex: item.itemIndex,
                    priorGrams: nil
                )
            )
        }
        return lines
    }

    private func correctionLines(from pending: PendingActionDTO) -> [ConfirmLine] {
        guard let entryId = pending.payload.entryId else { return [] }
        let index = pending.payload.itemIndex ?? 0
        let match = entries.first { $0.uuid.uuidString == entryId }
        let prior = match.flatMap { entry in entry.items.indices.contains(index) ? entry.items[index] : nil }
        if pending.payload.correctionOp == "remove" {
            return [
                ConfirmLine(
                    id: entryId,
                    name: prior?.name ?? pending.payload.reason ?? "",
                    foodId: prior?.foodId ?? "",
                    grams: prior?.grams ?? 0,
                    per100g: prior?.per100gMacros ?? .zero,
                    source: prior?.source ?? "diary",
                    citationUrl: nil,
                    portionLabel: nil,
                    family: prior?.ingredientFamily ?? "",
                    entryId: entryId,
                    itemIndex: index,
                    priorGrams: prior?.grams
                )
            ]
        }
        return pending.payload.resolvedItems.map { item in
            ConfirmLine(
                id: "\(entryId)-\(index)",
                name: item.displayName,
                foodId: item.foodId,
                grams: item.grams,
                per100g: item.per100g,
                source: item.source,
                citationUrl: item.citationUrl,
                portionLabel: item.portionLabel,
                family: item.family ?? prior?.ingredientFamily ?? "",
                entryId: entryId,
                itemIndex: index,
                priorGrams: prior?.grams
            )
        }
    }

    private func confirmPending() {
        let level = settings.first?.assistanceLevel ?? .fullAssist
        guard let outcome = CapyConfirmApplier.applyConfirm(
            lines: pendingLines,
            correctionOp: pendingCorrectionOp,
            mealSlot: pendingMealSlot,
            dayKey: todayKey,
            entries: Array(entries),
            target: target,
            eaten: eaten,
            assistance: level,
            in: modelContext
        ) else { return }
        finishConfirm(reply: outcome.reply)
    }

    private func finishConfirm(reply: String) {
        showConfirm = false
        pendingLines = []
        pendingCorrectionOp = nil
        messages.append(ChatBubble(role: .capy, text: reply))
        Task {
            try? await CapyThreadService.appendAssistant(reply, clearWorkingMemory: true)
        }
    }

    private func confirmDeletePending() {
        guard let pending = pendingDelete else {
            showDeleteConfirm = false
            return
        }
        let outcome = CapyConfirmApplier.applyDelete(
            pending: pending,
            entries: Array(entries),
            in: modelContext
        )
        finishDeleteConfirm(reply: outcome.reply)
    }

    private func cancelDeletePending() {
        showDeleteConfirm = false
        pendingDelete = nil
    }

    private func finishDeleteConfirm(reply: String) {
        showDeleteConfirm = false
        pendingDelete = nil
        messages.append(ChatBubble(role: .capy, text: reply))
        Task {
            try? await CapyThreadService.appendAssistant(reply, clearWorkingMemory: true)
        }
    }
}
