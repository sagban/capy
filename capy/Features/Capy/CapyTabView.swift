import SwiftUI
import SwiftData

struct CapyTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.scenePhase) private var scenePhase
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]
    @Query private var entries: [MealEntry]
    @Query private var settings: [AppSettings]
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    @State private var draft = ""
    @State private var messages: [ChatBubble] = []
    @State private var showConfirm = false
    @State private var showManualLog = false
    @State private var pendingLines: [ConfirmLine] = []
    @State private var pendingMealSlot = ""
    @State private var pendingCorrectionOp: String?
    @State private var isSending = false
    @State private var lastUtterance = ""
    @State private var lastAction: ClientActionDTO?
    @State private var speech = SpeechInputController()
    @FocusState private var talkFocused: Bool
    @State private var showMemory = false
    @State private var didLoadThread = false
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
                            if messages.isEmpty { starterPrompts }
                            ForEach(messages) { message in
                                chatBubble(message)
                                    .id(message.id)
                            }
                            if isSending {
                                ProgressView()
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 10)
                                    .accessibilityLabel("Capy is typing")
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
                        if let last = messages.last?.id {
                            withAnimation(.easeOut(duration: 0.2)) {
                                proxy.scrollTo(last, anchor: .bottom)
                            }
                        }
                    }
                }
            }
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
            .onAppear {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
                loadThreadIfNeeded()
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
            ForEach(Self.starters, id: \.self) { prompt in
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
            }
        }
        .padding(.top, 8)
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
                if !message.suggestions.isEmpty {
                    suggestionCards(message.suggestions)
                }
                if message.manualLog {
                    Button("Manual Log") { showManualLog = true }
                        .font(.subheadline.weight(.semibold))
                }
            }
            if message.role != .user { Spacer(minLength: 48) }
        }
    }

    private func suggestionCards(_ options: [SuggestionOptionDTO]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(options, id: \.id) { option in
                VStack(alignment: .leading, spacing: 4) {
                    Text(option.title)
                        .font(.subheadline.weight(.semibold))
                    let foods = option.items.map(\.displayName).filter { !$0.isEmpty }
                    if !foods.isEmpty {
                        Text(foods.joined(separator: ", "))
                            .font(.caption)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                    if let totals = option.totals {
                        let mark = option.fit == "over" ? "over the meal budget" : "fits"
                        Text("\(Int(totals.calories.rounded())) cal · \(Int(totals.proteinG.rounded())) g protein · \(mark)")
                            .font(.caption)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                    Button("Log this") {
                        send(action: ClientActionDTO(type: "pick_option", id: option.id), echo: option.title)
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.capy.accent)
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.capy.surfaceElevated, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
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
                }
                .accessibilityLabel("Send")
            } else {
                Button {
                    dismissTalkKeyboard()
                    speech.toggle()
                } label: {
                    Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.fill")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(speech.isRecording ? Color.capy.budgetCalories : Color.capy.textPrimary)
                        .frame(width: 32, height: 32)
                }
                .accessibilityLabel(speech.isRecording ? "Stop listening" : "Speak to Capy")
            }
        }
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
        .shadow(color: Color.black.opacity(0.08), radius: 8, y: 2)
    }

    private func loadThreadIfNeeded() {
        guard !didLoadThread else { return }
        didLoadThread = true
        let thread = ConversationMemoryStore.thread(in: modelContext)
        let turns = ConversationMemoryStore.orderedTurns(thread)
        // Drop the retired fake opener persisted by older builds.
        let legacyOpener = "what did you have to eat?"
        let visible = turns.filter {
            !($0.role != .user && $0.text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == legacyOpener)
        }
        guard !visible.isEmpty else { return }
        messages = visible.map { turn in
            ChatBubble(
                role: turn.role == .user ? .user : .capy,
                text: turn.text
            )
        }
    }

    private func handleDayRolloverIfNeeded() {
        let today = todayKey
        if !lastConversationDayKey.isEmpty, lastConversationDayKey != today {
            let priorCount = entries.filter { $0.dayKey == lastConversationDayKey && $0.confirmed }.count
            ConversationMemoryStore.noteDayRollover(
                previousDayKey: lastConversationDayKey,
                mealCount: priorCount,
                in: modelContext
            )
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
        ConversationMemoryStore.appendTurn(role: .assistant, text: text, in: modelContext)
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
        messages.append(ChatBubble(role: .user, text: text))
        ConversationMemoryStore.appendTurn(role: .user, text: text, in: modelContext)
        draft = ""
        lastUtterance = text
        lastAction = nil
        isSending = true
        Task { await interpret(utterance: text, action: nil) }
    }

    private func send(action: ClientActionDTO, echo: String) {
        guard !isSending else { return }
        messages.append(ChatBubble(role: .user, text: echo))
        ConversationMemoryStore.appendTurn(role: .user, text: echo, in: modelContext)
        lastUtterance = ""
        lastAction = action
        isSending = true
        Task { await interpret(utterance: "", action: action) }
    }

    private func retryLast() {
        guard !isSending else { return }
        isSending = true
        messages.removeAll { $0.role == .error }
        Task { await interpret(utterance: lastUtterance, action: lastAction) }
    }

    @MainActor
    private func interpret(utterance: String, action: ClientActionDTO?) async {
        defer { isSending = false }
        let request = ContextBuilder.buildInterpretRequest(
            utterance: utterance,
            dayKey: todayKey,
            action: action,
            modelContext: modelContext
        )
        do {
            let response = try await AgentClient.shared.interpretMeal(request)
            if response.warnings.contains("agent_unavailable") {
                messages.append(ChatBubble(role: .error, text: ""))
                return
            }
            if let proposals = response.memoryProposals, !proposals.isEmpty {
                LongTermMemoryStore.apply(proposals: proposals, in: modelContext)
            }
            let reply = response.assistantMessage.trimmingCharacters(in: .whitespacesAndNewlines)
            let suggestions = response.suggestionOptions ?? []
            let manual = response.pendingAction?.payload.manualLog == true
            let showed = !reply.isEmpty || !suggestions.isEmpty || manual || response.pendingAction != nil
            if !reply.isEmpty || !suggestions.isEmpty || manual {
                messages.append(
                    ChatBubble(
                        role: .capy,
                        text: reply,
                        suggestions: suggestions,
                        manualLog: manual
                    )
                )
                ConversationMemoryStore.appendTurn(
                    role: .assistant,
                    text: reply,
                    structuredPayload: response.structuredPayloadJSON(),
                    in: modelContext
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
        case .clarifyFood, .clarifyPortion:
            break
        }
    }

    private func confirmLines(from items: [ResolvedItemDTO]) -> [ConfirmLine] {
        items.enumerated().compactMap { index, item in
            guard item.grams > 0 else { return nil }
            return ConfirmLine(
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
        }
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
                    per100g: prior.flatMap { ContextBuilder.per100g(of: $0) } ?? .zero,
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
        if pendingCorrectionOp == "remove", let line = pendingLines.first, let entryId = line.entryId {
            if let entry = entries.first(where: { $0.uuid.uuidString == entryId }) {
                let index = line.itemIndex ?? 0
                if entry.items.indices.contains(index) {
                    let item = entry.items[index]
                    entry.items.remove(at: index)
                    modelContext.delete(item)
                }
                if entry.items.isEmpty {
                    modelContext.delete(entry)
                }
            }
            finishConfirm(reply: "removed.")
            return
        }

        if let line = pendingLines.first, let entryId = line.entryId,
           let entry = entries.first(where: { $0.uuid.uuidString == entryId }) {
            let index = line.itemIndex ?? 0
            guard entry.items.indices.contains(index) else { return }
            let item = entry.items[index]
            let macros = line.macros
            let oldGrams = item.grams
            item.name = line.name
            item.grams = line.grams
            item.calories = macros.calories
            item.proteinG = macros.proteinG
            item.carbsG = macros.carbsG
            item.fatG = macros.fatG
            item.foodId = line.foodId
            item.ingredientFamily = line.family
            item.source = line.source
            RecentCorrectionStore.append(
                text: "\(line.name): \(Int(oldGrams))g → \(Int(line.grams))g",
                dayKey: todayKey
            )
            let left = MacroTotals.remaining(target: target, eaten: eaten)
            finishConfirm(reply: "updated — \(Int(macros.calories)) cal. \(Int(left.calories)) cal left.")
            return
        }

        let items = pendingLines.map { line in
            let macros = line.macros
            return MealEntryItem(
                name: line.name,
                grams: line.grams,
                calories: macros.calories,
                proteinG: macros.proteinG,
                carbsG: macros.carbsG,
                fatG: macros.fatG,
                foodId: line.foodId,
                ingredientFamily: line.family,
                source: line.source
            )
        }
        guard !items.isEmpty else { return }
        let entry = MealEntry(
            dayKey: todayKey,
            mealSlot: pendingMealSlot.isEmpty ? nil : pendingMealSlot,
            originalUserText: items.map(\.name).joined(separator: ", "),
            confirmed: true,
            items: []
        )
        modelContext.insert(entry)
        for item in items {
            item.entry = entry
            entry.items.append(item)
        }
        let added = items.reduce(MacroTotals.zero) { partial, item in
            partial + MacroTotals(
                calories: item.calories,
                proteinG: item.proteinG,
                carbsG: item.carbsG,
                fatG: item.fatG
            )
        }
        let left = MacroTotals.remaining(
            target: target,
            eaten: eaten + added
        )
        let names = items.map(\.name).joined(separator: " and ")
        let level = settings.first?.assistanceLevel ?? .fullAssist
        let reply: String
        if level == .quiet {
            reply = "logged \(names). \(Int(left.calories)) left."
        } else {
            reply = "logged \(names). \(Int(added.calories)) cal. \(Int(left.calories)) cal left."
        }
        finishConfirm(reply: reply)
    }

    private func finishConfirm(reply: String) {
        showConfirm = false
        pendingLines = []
        pendingCorrectionOp = nil
        ConversationMemoryStore.clearOpenDraft(in: modelContext)
        messages.append(ChatBubble(role: .capy, text: reply))
        ConversationMemoryStore.appendTurn(role: .assistant, text: reply, in: modelContext)
    }
}

struct ChatBubble: Identifiable {
    enum Role { case capy, user, error }
    let id: UUID
    let role: Role
    let text: String
    var chips: [ClarifyOptionDTO] = []
    var suggestions: [SuggestionOptionDTO] = []
    var resolvedNames: [String] = []
    var waitingNames: [String] = []
    var manualLog: Bool = false
    var freeTextGrams: Bool = false
    var chipAction: String = "pick_candidate"

    init(
        id: UUID = UUID(),
        role: Role,
        text: String,
        chips: [ClarifyOptionDTO] = [],
        suggestions: [SuggestionOptionDTO] = [],
        resolvedNames: [String] = [],
        waitingNames: [String] = [],
        manualLog: Bool = false,
        freeTextGrams: Bool = false,
        chipAction: String = "pick_candidate"
    ) {
        self.id = id
        self.role = role
        self.text = text
        self.chips = chips
        self.suggestions = suggestions
        self.resolvedNames = resolvedNames
        self.waitingNames = waitingNames
        self.manualLog = manualLog
        self.freeTextGrams = freeTextGrams
        self.chipAction = chipAction
    }
}
