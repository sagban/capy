import SwiftUI

/// Macro strip used on Manual Log details and composition portion screens.
struct FoodMacroBadgeRow: View {
    @Environment(\.unitPreferences) private var units

    let calories: Double
    let carbsG: Double
    let fatG: Double
    let proteinG: Double

    var body: some View {
        HStack(spacing: 12) {
            calorieBadge(units.formattedEnergy(calories))
            macroBadge(letter: "C", value: Int(carbsG.rounded()), color: Color.capy.budgetCarbs)
            macroBadge(letter: "F", value: Int(fatG.rounded()), color: Color.capy.budgetFat)
            macroBadge(letter: "P", value: Int(proteinG.rounded()), color: Color.capy.budgetProtein)
        }
        .padding(.vertical, 2)
    }

    private func calorieBadge(_ text: String) -> some View {
        HStack(spacing: 3) {
            Image(systemName: "flame.fill")
                .font(.caption2)
                .foregroundStyle(Color.capy.budgetCalories)
            Text(text)
                .font(.caption.weight(.medium))
                .foregroundStyle(Color.capy.textSecondary)
        }
    }

    private func macroBadge(letter: String, value: Int, color: Color) -> some View {
        HStack(spacing: 4) {
            Text(letter)
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 16, height: 16)
                .background(color, in: Circle())
            Text("\(value)")
                .font(.caption.weight(.medium))
                .foregroundStyle(Color.capy.textSecondary)
        }
    }
}
