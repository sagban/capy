import SwiftUI

/// Cappy type system: SF Rounded for warm, friendly doer UI (no custom font bundle).
/// Macro numbers use tabular digits so rings/lists don’t jitter.
enum CapyTypography {
    /// App-wide design: rounded SF Pro.
    static let design: Font.Design = .rounded

    static func title(_ size: CGFloat = 22, weight: Font.Weight = .semibold) -> Font {
        .system(size: size, weight: weight, design: design)
    }

    static func body(_ size: CGFloat = 17, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: design)
    }

    static func callout(weight: Font.Weight = .regular) -> Font {
        .system(size: 16, weight: weight, design: design)
    }

    static func caption(weight: Font.Weight = .regular) -> Font {
        .system(size: 12, weight: weight, design: design)
    }

    /// Calories / grams — rounded + fixed-width digits.
    static func metric(_ size: CGFloat = 17, weight: Font.Weight = .semibold) -> Font {
        .system(size: size, weight: weight, design: design).monospacedDigit()
    }
}

extension View {
    /// Prefer SF Rounded across the app (titles, body, captions inherit design).
    func capyTypography() -> some View {
        fontDesign(CapyTypography.design)
    }
}
