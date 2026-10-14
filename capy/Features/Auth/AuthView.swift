import SwiftUI

struct AuthView: View {
    @Environment(AuthManager.self) private var auth

    private enum Mode {
        case signIn, createAccount
    }

    private enum Field {
        case email, password
    }

    @State private var mode: Mode = .signIn
    @State private var email = ""
    @State private var password = ""
    @FocusState private var focusedField: Field?

    private var trimmedEmail: String {
        email.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var canSubmit: Bool {
        !auth.isBusy && trimmedEmail.contains("@") && !password.isEmpty
    }

    var body: some View {
        ZStack {
            CapyScreenBackground()
            ScrollView {
                VStack(spacing: 28) {
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
                    .padding(.top, 72)

                    GlassPanel {
                        VStack(spacing: 16) {
                            emailForm
                            divider
                            googleButton
                        }
                    }
                    .padding(.horizontal, 24)

                    messages
                }
                .padding(.bottom, 32)
            }
            .scrollDismissesKeyboard(.interactively)
        }
    }

    private var emailForm: some View {
        VStack(spacing: 12) {
            TextField("Email", text: $email)
                .textContentType(.username)
                .keyboardType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.next)
                .focused($focusedField, equals: .email)
                .onSubmit { focusedField = .password }
                .modifier(AuthFieldStyle())

            SecureField("Password", text: $password)
                .textContentType(mode == .signIn ? .password : .newPassword)
                .submitLabel(.go)
                .focused($focusedField, equals: .password)
                .onSubmit(submit)
                .modifier(AuthFieldStyle())

            Button(action: submit) {
                Text(primaryTitle)
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color.capy.accent)
            .disabled(!canSubmit)

            HStack {
                Button(mode == .signIn ? "Create account" : "I have an account") {
                    mode = mode == .signIn ? .createAccount : .signIn
                    auth.clearMessages()
                }
                Spacer()
                if mode == .signIn {
                    Button("Forgot password?") {
                        focusedField = nil
                        Task { await auth.sendPasswordReset(email: trimmedEmail) }
                    }
                    .disabled(auth.isBusy)
                }
            }
            .font(.footnote.weight(.medium))
            .foregroundStyle(Color.capy.accent)
        }
    }

    private var divider: some View {
        HStack(spacing: 12) {
            Rectangle().frame(height: 1)
            Text("or")
                .font(.footnote)
            Rectangle().frame(height: 1)
        }
        .foregroundStyle(Color.capy.textSecondary.opacity(0.6))
    }

    private var googleButton: some View {
        Button {
            focusedField = nil
            Task { await auth.signInWithGoogle() }
        } label: {
            HStack {
                Image(systemName: "g.circle.fill")
                Text("Continue with Google")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
        }
        .buttonStyle(.bordered)
        .tint(Color.capy.accent)
        .disabled(auth.isBusy)
    }

    @ViewBuilder
    private var messages: some View {
        if let error = auth.errorMessage {
            Text(error)
                .font(.footnote)
                .foregroundStyle(Color.capy.warning)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        } else if let notice = auth.noticeMessage {
            Text(notice)
                .font(.footnote)
                .foregroundStyle(Color.capy.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
    }

    private var primaryTitle: String {
        if auth.isBusy { return mode == .signIn ? "Signing in…" : "Creating account…" }
        return mode == .signIn ? "Sign in" : "Create account"
    }

    private func submit() {
        guard canSubmit else { return }
        focusedField = nil
        let email = trimmedEmail
        let password = password
        Task {
            switch mode {
            case .signIn: await auth.signIn(email: email, password: password)
            case .createAccount: await auth.createAccount(email: email, password: password)
            }
        }
    }
}

private struct AuthFieldStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .foregroundStyle(Color.capy.textPrimary)
            .background(
                Color.capy.surfaceElevated,
                in: RoundedRectangle(cornerRadius: 12, style: .continuous)
            )
    }
}
