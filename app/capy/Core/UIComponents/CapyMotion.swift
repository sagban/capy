import SwiftUI

/// Soft bounce-in for chat bubbles and list rows.
struct CapyAppearMotion: ViewModifier {
    var edge: Edge = .bottom
    @State private var shown = false

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown ? 0 : (edge == .bottom ? 10 : -10))
            .onAppear {
                withAnimation(.spring(response: 0.38, dampingFraction: 0.86)) {
                    shown = true
                }
            }
    }
}

extension View {
    func capyAppear(from edge: Edge = .bottom) -> some View {
        modifier(CapyAppearMotion(edge: edge))
    }
}

/// Three soft dots — Capy is working on a reply.
struct CapyTypingIndicator: View {
    @State private var bouncing = false

    var body: some View {
        HStack(spacing: 6) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(Color.capy.textSecondary.opacity(0.55))
                    .frame(width: 7, height: 7)
                    .offset(y: bouncing ? -4 : 0)
                    .animation(
                        .easeInOut(duration: 0.42)
                            .repeatForever(autoreverses: true)
                            .delay(Double(index) * 0.14),
                        value: bouncing
                    )
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.capy.surfaceElevated, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityLabel("Capy is typing")
        .onAppear { bouncing = true }
    }
}

/// Compact row for “loading earlier” / inline waits.
struct CapyInlineLoader: View {
    var label: String = "Loading…"

    var body: some View {
        HStack(spacing: 8) {
            ProgressView()
                .controlSize(.small)
                .tint(Color.capy.accent)
            Text(label)
                .font(.caption)
                .foregroundStyle(Color.capy.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
    }
}

/// Pulsing mic affordance while speech is live.
struct CapyRecordingPulse: ViewModifier {
    var active: Bool

    func body(content: Content) -> some View {
        content
            .scaleEffect(active ? 1.08 : 1)
            .animation(
                active
                    ? .easeInOut(duration: 0.7).repeatForever(autoreverses: true)
                    : .spring(response: 0.3, dampingFraction: 0.8),
                value: active
            )
    }
}

extension View {
    func capyRecordingPulse(_ active: Bool) -> some View {
        modifier(CapyRecordingPulse(active: active))
    }
}

/// Full-screen soft blocker while the first thread page loads.
struct CapyThreadLoadingOverlay: View {
    var body: some View {
        VStack(spacing: 14) {
            ProgressView()
                .controlSize(.regular)
                .tint(Color.capy.accent)
            Text("Loading chat…")
                .font(.subheadline)
                .foregroundStyle(Color.capy.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.capy.background.opacity(0.72))
        .accessibilityLabel("Loading chat")
        .transition(.opacity)
    }
}
