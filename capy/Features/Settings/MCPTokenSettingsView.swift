import SwiftUI
import UIKit

struct MCPTokenSettingsView: View {
    @State private var issued: MCPAccessToken?
    @State private var busy = false
    @State private var note = ""

    var body: some View {
        Form {
            Section {
                Text("Copy a token for an MCP client. It uses this account and lasts 1 hour.")
                    .font(.subheadline)
                    .foregroundStyle(Color.capy.textSecondary)
            }

            if let issued {
                Section("Token") {
                    Text(issued.accessToken)
                        .font(.footnote.monospaced())
                        .textSelection(.enabled)
                    Button("Copy token") { copy(issued.accessToken, confirmation: "Token copied.") }
                }
                Section("MCP config") {
                    Text(issued.configJSON)
                        .font(.footnote.monospaced())
                        .textSelection(.enabled)
                    Button("Copy config") { copy(issued.configJSON, confirmation: "Config copied.") }
                }
            }

            Section {
                Button(busy ? "Getting token…" : "Get token") {
                    Task { await load() }
                }
                .disabled(busy)
                if !note.isEmpty {
                    Text(note)
                        .font(.footnote)
                        .foregroundStyle(Color.capy.textSecondary)
                }
            }
        }
        .navigationTitle("MCP token")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func load() async {
        busy = true
        note = ""
        defer { busy = false }
        do {
            let minted = try await AgentClient.shared.exchangeAccessToken()
            issued = minted
            copy(minted.accessToken, confirmation: "Token copied. It lasts 1 hour.")
        } catch {
            note = "Couldn’t get a token. Try again."
        }
    }

    private func copy(_ value: String, confirmation: String) {
        UIPasteboard.general.string = value
        note = confirmation
    }
}
