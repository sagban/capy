import SwiftUI

/// Continues the system launch screen with the same layout (dark field + square mark).
/// Avoid circle-clipping here — that caused a flash of a “boxed” then round image.
struct SplashView: View {
    @State private var showChrome = false

    var body: some View {
        ZStack {
            Color.capy.launchBackground
                .ignoresSafeArea()

            Image("CapyLaunchIcon")
                .resizable()
                .scaledToFit()
                .frame(width: 128, height: 128)
                // Match App Icon squircle feel without a hard circle crop flash.
                .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))

            VStack(spacing: 14) {
                Text("Capy")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.white.opacity(0.92))
                ProgressView()
                    .controlSize(.small)
                    .tint(Color.capy.accent)
            }
            .offset(y: 110)
            .opacity(showChrome ? 1 : 0)
        }
        .onAppear {
            // First frame ≈ system launch; chrome fades after so there’s no shape pop.
            withAnimation(.easeOut(duration: 0.28).delay(0.05)) {
                showChrome = true
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Capy is loading")
    }
}

#Preview {
    SplashView()
}
