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
    @State private var pendingCalories = 450.0
    @State private var pendingProtein = 30.0
    @State private var pendingCarbs = 40.0
    @State private var pendingFat = 15.0
    @State private var pendingGrams = 250.0
    @State private var pendingMealSlot = ""
    @State private var speech = SpeechInputController()
    @FocusState private var talkFocused: Bool

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
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
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
                SettingsToolbarButton()
            }
            .keyboardDoneToolbar()
            .sheet(isPresented: $showConfirm) {
                MealConfirmationSheet(
                    name: pendingName,
                    grams: $pendingGrams,
                    mealSlot: $pendingMealSlot,
                    calories: pendingCalories,
                    protein: pendingProtein,
                    carbs: pendingCarbs,
                    fat: pendingFat,
                    onConfirm: confirmPending
                )
                .presentationDetents([.medium])
            }
            .onAppear {
                MealTypeCatalog.seedIfNeeded(in: modelContext)
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

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        speech.stop()
        talkFocused = false
        Keyboard.dismiss()
        messages.append(ChatBubble(role: .user, text: text))
        draft = ""
        pendingName = text
        pendingCalories = 520
        pendingProtein = 35
        pendingCarbs = 48
        pendingFat = 18
        pendingGrams = 300
        pendingMealSlot = MealTypeCatalog.suggestedName(from: mealTypes.filter(\.isEnabled)) ?? ""
        showConfirm = true
        let level = settings.first?.assistanceLevel ?? .fullAssist
        if level == .quiet {
            messages.append(ChatBubble(role: .capy, text: "confirm portions when you’re ready."))
        } else {
            messages.append(ChatBubble(role: .capy, text: "got it — confirm the portions and I’ll bank it."))
        }
    }

    private func confirmPending() {
        let item = MealEntryItem(
            name: pendingName,
            grams: pendingGrams,
            calories: pendingCalories * (pendingGrams / 300),
            proteinG: pendingProtein * (pendingGrams / 300),
            carbsG: pendingCarbs * (pendingGrams / 300),
            fatG: pendingFat * (pendingGrams / 300)
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
        if level == .quiet {
            messages.append(ChatBubble(role: .capy, text: "logged. \(Int(left.calories)) left."))
        } else {
            messages.append(ChatBubble(
                role: .capy,
                text: "logged — ~\(Int(item.calories)) cal banked. \(Int(left.calories)) cal left."
            ))
        }
    }
}

struct ChatBubble: Identifiable {
    enum Role { case capy, user }
    let id = UUID()
    let role: Role
    let text: String
}
