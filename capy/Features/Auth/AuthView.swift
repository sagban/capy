import SwiftUI

struct AuthView: View {
    @Environment(AuthManager.self) private var auth

    var body: some View {
        ZStack {
            CapyScreenBackground()
            VStack(spacing: 28) {
                Spacer()
                VStack(spacing: 8) {
                    Text("Capy")
                        .font(.system(size: 48, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.capy.textPrimary)
                    Text("Food gets handled. You answer in plain words.")
                        .font(.body)
                        .foregroundStyle(Color.capy.textSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }

                GlassPanel {
                    VStack(spacing: 16) {
                        Button {
                            Task { await auth.signInWithGoogle() }
                        } label: {
                            HStack {
                                Image(systemName: "g.circle.fill")
                                Text(auth.isBusy ? "Signing in…" : "Continue with Google")
                                    .fontWeight(.semibold)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.capy.accent)
                        .disabled(auth.isBusy)

                        Text("Sign in with Apple comes later.")
                            .font(.footnote)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
                .padding(.horizontal, 24)

                if let error = auth.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(Color.capy.warning)
                        .padding(.horizontal)
                }

                Spacer()
            }
        }
    }
}
