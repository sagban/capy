import SwiftUI

/// App Color Palette tokens — see `docs/design/color-palette.md`.
/// Use these instead of ad-hoc hex in feature views.
enum CapyColors {
    static let background = Color("CapyBackground")
    /// Matches AppIcon canvas (`#141819`) for launch / splash only.
    static let launchBackground = Color("CapyLaunchBackground")
    static let surface = Color("CapySurface")
    static let surfaceElevated = Color("CapySurfaceElevated")
    static let textPrimary = Color("CapyTextPrimary")
    static let textSecondary = Color("CapyTextSecondary")
    static let accent = Color("CapyAccent")
    static let accentSoft = Color("CapyAccentSoft")
    static let warning = Color("CapyWarning")
    static let budgetCalories = Color("CapyBudgetCalories")
    static let budgetProtein = Color("CapyBudgetProtein")
    static let budgetCarbs = Color("CapyBudgetCarbs")
    static let budgetFat = Color("CapyBudgetFat")
}

extension Color {
    enum capy {
        static let background = CapyColors.background
        static let launchBackground = CapyColors.launchBackground
        static let surface = CapyColors.surface
        static let surfaceElevated = CapyColors.surfaceElevated
        static let textPrimary = CapyColors.textPrimary
        static let textSecondary = CapyColors.textSecondary
        static let accent = CapyColors.accent
        static let accentSoft = CapyColors.accentSoft
        static let warning = CapyColors.warning
        static let budgetCalories = CapyColors.budgetCalories
        static let budgetProtein = CapyColors.budgetProtein
        static let budgetCarbs = CapyColors.budgetCarbs
        static let budgetFat = CapyColors.budgetFat
    }
}
