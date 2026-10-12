import SwiftUI
import SwiftData

struct CapyTabView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \DailyTarget.effectiveDate, order: .reverse) private var targets: [DailyTarget]
    @Query private var entries: [MealEntry]
    @Query private var settings: [AppSettings]
    @Query(sort: \MealType.sortOrder) private var mealTypes: [MealType]

    @State private var draft = ""
    @State private var messages: [ChatBubble] = [
        ChatBubble(role: .capy, text: "what did you have to eat?"),
    ]
    @State private var showConfirm = false
    @State private var pendingName = ""
    @State private var pendingFoodId = ""
    @State private var pendingFamily = ""
    @State private var pendingCalories = 450.0
    @State private var pendingProtein = 30.0
    @State private var pendingCarbs = 40.0
    @State private var pendingFat = 15.0
    @State private var pendingBaseGrams = 100.0
    @State private var pendingGrams = 100.0
    @State private var pendingMealSlot = ""
    @State private var isSending = false
    @State private var speech = SpeechInputController()
    @FocusState private var talkFocused: Bool
    @State private var showMemory = false
    @State private var didLoadThread = false
    @AppStorage("capy.lastConversationDayKey") private var lastConversationDayKey = ""

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

    private var canSend: Bool {
        !isSending && !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        NavigationStack {
            ZStack {
                CapyScreenBackground()
                    .onTapGesture {
                        talkFocused = false
                        Keyboard.dismiss()
                    }

                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            ForEach(messages) { message in
                                chatBubble(message)
                                    .id(message.id)
                            }
                        }
                        .padding(.horizontal)
                        .padding(.top, 12)
                        .padding(.bottom, 16)
                    }
                    .scrollDismissesKeyboard(.interactively)
                    .onTapGesture {
                        talkFocused = false
                        Keyboard.dismiss()
                    }
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
            .keyboardDoneToolbar()
            .sheet(isPresented: $showConfirm) {
                MealConfirmationSheet(
                    name: pendingName,
                    grams: $pendingGrams,
                    baseGrams: pendingBaseGrams,
                    mealSlot: $pendingMealSlot,
                    calories: pendingCalories,
                    protein: pendingProtein,
                    carbs: pendingCarbs,
                    fat: pendingFat,
                    onConfirm: confirmPending
                )
                .presentationDetents([.medium])
            }
            .sheet(isPresented: $showMemory) {
                MemorySheetView()
            }
            .onAppear {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
                try? SeedImporter.importIfNeeded(into: modelContext)
                loadThreadIfNeeded()
                handleDayRolloverIfNeeded()
            }
            .onChange(of: speech.transcript) { _, newValue in
                guard speech.isRecording, !newValue.isEmpty else { return }
                draft = newValue
            }
            .onChange(of: speech.isRecording) { wasRecording, isRecording in
                if wasRecording && !isRecording {
                    let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !text.isEmpty {
                        talkFocused = false
                    }
                }
            }
            .onDisappear {
                speech.stop()
            }
        }
    }

    private func chatBubble(_ message: ChatBubble) -> some View {
        HStack {
            if message.role == .user { Spacer(minLength: 48) }
            Text(message.text)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    message.role == .capy
                    ? Color.capy.surfaceElevated
                    : Color.capy.accent,
                    in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                )
                .foregroundStyle(
                    message.role == .capy
                    ? Color.capy.textPrimary
                    : Color.white
                )
            if message.role == .capy { Spacer(minLength: 48) }
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
                    talkFocused = false
                    Keyboard.dismiss()
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
        guard !turns.isEmpty else { return }
        messages = turns.map { turn in
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

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }
        speech.stop()
        talkFocused = false
        Keyboard.dismiss()
        messages.append(ChatBubble(role: .user, text: text))
        ConversationMemoryStore.appendTurn(role: .user, text: text, in: modelContext)
        draft = ""
        isSending = true
        messages.append(ChatBubble(role: .capy, text: "…"))

        Task {
            await interpret(utterance: text)
        }
    }

    @MainActor
    private func interpret(utterance: String) async {
        defer { isSending = false }
        let request = ContextBuilder.buildInterpretRequest(
            utterance: utterance,
            dayKey: todayKey,
            modelContext: modelContext
        )
        do {
            let response = try await AgentClient.shared.interpretMeal(request)
            if let proposals = response.memoryProposals, !proposals.isEmpty {
                LongTermMemoryStore.apply(proposals: proposals, in: modelContext)
            }
            let reply = response.assistantMessage.trimmingCharacters(in: .whitespacesAndNewlines)
            let display = reply.isEmpty ? fallbackMessage(for: response) : reply
            replaceLastCapyMessage(with: display)
            ConversationMemoryStore.appendTurn(
                role: .assistant,
                text: display,
                structuredPayload: response.structuredPayloadJSON(),
                in: modelContext
            )
            presentConfirmationIfNeeded(response)
        } catch {
            let msg = "couldn’t reach the harness (\(EnvironmentConfig.environment.rawValue)). \(error.localizedDescription)"
            replaceLastCapyMessage(with: msg)
            ConversationMemoryStore.appendTurn(role: .assistant, text: msg, in: modelContext)
        }
    }

    private func fallbackMessage(for response: InterpretMealResponse) -> String {
        switch response.intent {
        case .clarify:
            return response.clarifyingQuestion ?? "quick check?"
        case .updateMemory:
            return "saved that for later"
        case .suggestMeal:
            return response.candidates.first.map { "fits remaining: \($0.displayName)" } ?? "nothing that fits cleanly"
        case .logMeal, .correctMeal:
            return "confirm portions when you’re ready."
        default:
            return "not sure what to do with that"
        }
    }

    private func replaceLastCapyMessage(with text: String) {
        if let idx = messages.indices.last, messages[idx].role == .capy {
            messages[idx] = ChatBubble(id: messages[idx].id, role: .capy, text: text)
        } else {
            messages.append(ChatBubble(role: .capy, text: text))
        }
    }

    private func presentConfirmationIfNeeded(_ response: InterpretMealResponse) {
        guard response.intent == .logMeal || response.intent == .correctMeal || response.intent == .suggestMeal else {
            return
        }
        guard let candidate = response.candidates.first else { return }
        let grams = candidate.grams ?? 100
        let macros: MacroTotals
        if let food = fetchFood(id: candidate.foodId) {
            macros = MacroMath.scale(per100g: food.per100g, grams: grams)
            pendingFoodId = food.id
            pendingFamily = food.ingredientFamily
        } else {
            // Fail closed on macros: no invented numbers — skip confirm sheet.
            return
        }
        pendingName = candidate.displayName
        pendingBaseGrams = grams
        pendingGrams = grams
        pendingCalories = macros.calories
        pendingProtein = macros.proteinG
        pendingCarbs = macros.carbsG
        pendingFat = macros.fatG
        pendingMealSlot = MealTypeCatalog.suggestedName(from: mealTypes.filter(\.isEnabled)) ?? ""
        showConfirm = true
    }

    private func fetchFood(id: String) -> Food? {
        var descriptor = FetchDescriptor<Food>(predicate: #Predicate { $0.id == id })
        descriptor.fetchLimit = 1
        return try? modelContext.fetch(descriptor).first
    }

    private func confirmPending() {
        let scale = pendingBaseGrams > 0 ? pendingGrams / pendingBaseGrams : 1
        let item = MealEntryItem(
            name: pendingName,
            grams: pendingGrams,
            calories: pendingCalories * scale,
            proteinG: pendingProtein * scale,
            carbsG: pendingCarbs * scale,
            fatG: pendingFat * scale,
            foodId: pendingFoodId,
            ingredientFamily: pendingFamily
        )
        let entry = MealEntry(
            dayKey: todayKey,
            mealSlot: pendingMealSlot.isEmpty ? nil : pendingMealSlot,
            originalUserText: pendingName,
            confirmed: true,
            items: [item]
        )
        modelContext.insert(entry)
        showConfirm = false
        let left = MacroTotals.remaining(target: target, eaten: MacroTotals(
            calories: eaten.calories + item.calories,
            proteinG: eaten.proteinG + item.proteinG,
            carbsG: eaten.carbsG + item.carbsG,
            fatG: eaten.fatG + item.fatG
        ))
        let level = settings.first?.assistanceLevel ?? .fullAssist
        let reply: String
        if DialPolicy.showsBenefitAfterLog(level) {
            reply = "logged — ~\(Int(item.calories)) cal banked. \(Int(left.calories)) cal left."
        } else if level == .quiet {
            reply = "logged. \(Int(left.calories)) left."
        } else {
            reply = "logged. \(Int(left.calories)) cal left."
        }
        messages.append(ChatBubble(role: .capy, text: reply))
        ConversationMemoryStore.appendTurn(role: .assistant, text: reply, in: modelContext)
    }
}

struct ChatBubble: Identifiable {
    enum Role { case capy, user }
    let id: UUID
    let role: Role
    let text: String

    init(id: UUID = UUID(), role: Role, text: String) {
        self.id = id
        self.role = role
        self.text = text
    }
}
