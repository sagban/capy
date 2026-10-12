import SwiftUI

struct CapyScreenBackground: View {
    var body: some View {
        Color.capy.background
            .ignoresSafeArea()
    }
}

struct GlassPanel<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        content()
            .padding()
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct SettingsToolbarButton: ToolbarContent {
    var body: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            NavigationLink {
                SettingsRootView()
            } label: {
                Image(systemName: "gearshape")
            }
            .accessibilityLabel("Settings")
        }
    }
}

struct BudgetBarView: View {
    let remaining: MacroTotals
    let target: MacroTotals
    let overTarget: Bool

    var body: some View {
        GlassPanel {
            VStack(alignment: .leading, spacing: 10) {
                Text(overTarget ? "0 left · over target" : "\(Int(remaining.calories.rounded())) cal left")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(overTarget ? Color.capy.warning : Color.capy.budgetCalories)
                    .accessibilityLabel("Calories remaining")

                HStack(spacing: 12) {
                    macroChip("P", remaining.proteinG, Color.capy.budgetProtein)
                    macroChip("C", remaining.carbsG, Color.capy.budgetCarbs)
                    macroChip("F", remaining.fatG, Color.capy.budgetFat)
                }

                ProgressView(value: min(1, max(0, 1 - remaining.calories / max(target.calories, 1))))
                    .tint(Color.capy.accent)
            }
        }
    }

    private func macroChip(_ label: String, _ grams: Double, _ color: Color) -> some View {
        Text("\(label) \(Int(grams.rounded()))g")
            .font(.subheadline.weight(.medium))
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Color.capy.accentSoft.opacity(0.55), in: Capsule())
    }
}
