import SwiftUI

/// Continues the static launch screen (same background + centered avatar) while launch work settles.
struct SplashView: View {
    @State private var appeared = false

    var body: some View {
        ZStack {
            CapyScreenBackground()

            Image("CapyLaunch")
                .scaleEffect(appeared ? 1.06 : 1)

            VStack(spacing: 14) {
                Text("Capy")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.capy.textPrimary)
                ProgressView()
                    .tint(Color.capy.accent)
            }
            .offset(y: 120)
            .opacity(appeared ? 1 : 0)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.45)) { appeared = true }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Capy is loading")
    }
}

#Preview {
    SplashView()
}
