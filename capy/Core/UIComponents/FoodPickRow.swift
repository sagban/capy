import SwiftUI

/// Shared list row for food / library picks (Manual Log + recipe/meal builder).
struct FoodPickRow: View {
    let title: String
    /// Portion reference grams shown after the title (e.g. default serving).
    var portionGrams: Double? = nil
    var subtitle: String = ""
    let detail: String
    var showsChevron: Bool = true

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(title)
                        .foregroundStyle(Color.primary)
                    if let portionGrams, portionGrams > 0 {
                        Text("\(Int(portionGrams.rounded())) g")
                            .font(.subheadline)
                            .foregroundStyle(Color.capy.textSecondary)
                    }
                }
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(Color.capy.textSecondary)
            }
            Spacer()
            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
        }
    }
}
