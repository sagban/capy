import Foundation
import SwiftData

enum AssistanceLevel: String, Codable, CaseIterable, Identifiable {
    case fullAssist
    case guided
    case quiet

    var id: String { rawValue }

    var title: String {
        switch self {
        case .fullAssist: "Full Assist"
        case .guided: "Guided"
        case .quiet: "Quiet"
        }
    }

    var subtitle: String {
        switch self {
        case .fullAssist: "Check-ins and a benefit after every log"
        case .guided: "One evening decision moment"
        case .quiet: "You talk; Capy stays quiet"
        }
    }
}

@Model
final class AppSettings {
    var onboardingCompleted: Bool
    var assistanceLevelRaw: String
    var guidedCheckInHour: Int
    var guidedCheckInMinute: Int
    var energyUnitRaw: String = EnergyUnit.kcal.rawValue
    var foodMassUnitRaw: String = FoodMassUnit.gram.rawValue
    var bodyMassUnitRaw: String = BodyMassUnit.kilogram.rawValue
    var weekStartRaw: String = WeekStartPreference.system.rawValue

    var assistanceLevel: AssistanceLevel {
        get { AssistanceLevel(rawValue: assistanceLevelRaw) ?? .guided }
        set { assistanceLevelRaw = newValue.rawValue }
    }

    var energyUnit: EnergyUnit {
        get { EnergyUnit(rawValue: energyUnitRaw) ?? .kcal }
        set { energyUnitRaw = newValue.rawValue }
    }

    var foodMassUnit: FoodMassUnit {
        get { FoodMassUnit(rawValue: foodMassUnitRaw) ?? .gram }
        set { foodMassUnitRaw = newValue.rawValue }
    }

    var bodyMassUnit: BodyMassUnit {
        get { BodyMassUnit(rawValue: bodyMassUnitRaw) ?? .kilogram }
        set { bodyMassUnitRaw = newValue.rawValue }
    }

    var weekStart: WeekStartPreference {
        get { WeekStartPreference(rawValue: weekStartRaw) ?? .system }
        set { weekStartRaw = newValue.rawValue }
    }

    var unitPreferences: UnitPreferences {
        UnitPreferences(
            energy: energyUnit,
            foodMass: foodMassUnit,
            bodyMass: bodyMassUnit,
            weekStart: weekStart
        )
    }

    init(
        onboardingCompleted: Bool = false,
        assistanceLevel: AssistanceLevel = .fullAssist,
        guidedCheckInHour: Int = 18,
        guidedCheckInMinute: Int = 0,
        energyUnit: EnergyUnit = .kcal,
        foodMassUnit: FoodMassUnit = .gram,
        bodyMassUnit: BodyMassUnit = .kilogram,
        weekStart: WeekStartPreference = .system
    ) {
        self.onboardingCompleted = onboardingCompleted
        self.assistanceLevelRaw = assistanceLevel.rawValue
        self.guidedCheckInHour = guidedCheckInHour
        self.guidedCheckInMinute = guidedCheckInMinute
        self.energyUnitRaw = energyUnit.rawValue
        self.foodMassUnitRaw = foodMassUnit.rawValue
        self.bodyMassUnitRaw = bodyMassUnit.rawValue
        self.weekStartRaw = weekStart.rawValue
    }
}

@Model
final class DailyTarget {
    var effectiveDate: Date
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    /// Defaults for lightweight migration when older stores lack this field.
    var splitRaw: String = MacroSplit.balanced.rawValue

    var macroSplit: MacroSplit {
        get { MacroSplit(rawValue: splitRaw) ?? .custom }
        set { splitRaw = newValue.rawValue }
    }

    init(
        effectiveDate: Date = Calendar.current.startOfDay(for: .now),
        calories: Double = 2000,
        proteinG: Double = 140,
        carbsG: Double = 200,
        fatG: Double = 65,
        macroSplit: MacroSplit = .balanced
    ) {
        self.effectiveDate = effectiveDate
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.splitRaw = macroSplit.rawValue
    }
}

@Model
final class UserPreference {
    var kindRaw: String
    var value: String
    var createdAt: Date

    var kind: PreferenceKind {
        get { PreferenceKind(rawValue: kindRaw) ?? .like }
        set { kindRaw = newValue.rawValue }
    }

    init(kind: PreferenceKind, value: String, createdAt: Date = .now) {
        self.kindRaw = kind.rawValue
        self.value = value
        self.createdAt = createdAt
    }
}

enum PreferenceKind: String, Codable, CaseIterable, Identifiable {
    case like
    case dislike
    case allergy
    case diet

    var id: String { rawValue }

    var title: String {
        switch self {
        case .like: "Preference"
        case .dislike: "Dislike"
        case .allergy: "Allergy"
        case .diet: "Diet"
        }
    }
}

@Model
final class MealType {
    var id: UUID
    var name: String
    var sortOrder: Int
    var isEnabled: Bool
    /// System defaults (Breakfast…Dinner) can be disabled but not deleted.
    var isSystem: Bool

    init(
        id: UUID = UUID(),
        name: String,
        sortOrder: Int,
        isEnabled: Bool = true,
        isSystem: Bool = false
    ) {
        self.id = id
        self.name = name
        self.sortOrder = sortOrder
        self.isEnabled = isEnabled
        self.isSystem = isSystem
    }
}

enum MealTypeCatalog {
    static let defaults: [(name: String, order: Int)] = [
        ("Breakfast", 0),
        ("Lunch", 1),
        ("Snacks", 2),
        ("Dinner", 3),
    ]

    static func seedIfNeeded(in context: ModelContext) {
        let descriptor = FetchDescriptor<MealType>()
        let existing = (try? context.fetch(descriptor)) ?? []
        guard existing.isEmpty else { return }
        for item in defaults {
            context.insert(
                MealType(name: item.name, sortOrder: item.order, isEnabled: true, isSystem: true)
            )
        }
    }

    /// Best-effort slot from clock time among currently enabled types.
    static func suggestedName(from enabled: [MealType], date: Date = .now) -> String? {
        guard !enabled.isEmpty else { return nil }
        let hour = Calendar.current.component(.hour, from: date)
        let preferred: String = switch hour {
        case 4..<11: "Breakfast"
        case 11..<15: "Lunch"
        case 15..<17: "Snacks"
        case 17..<22: "Dinner"
        default: "Snacks"
        }
        if let match = enabled.first(where: { $0.name == preferred }) {
            return match.name
        }
        return enabled.first?.name
    }
}

@Model
final class MealEntry {
    var timestamp: Date
    var dayKey: String
    var mealSlot: String?
    var originalUserText: String?
    var confirmed: Bool
    /// Stable id sent to the agent so repeat and correct target this entry.
    var uuid: UUID = UUID()
    @Relationship(deleteRule: .cascade, inverse: \MealEntryItem.entry)
    var items: [MealEntryItem]

    init(
        timestamp: Date = .now,
        dayKey: String,
        mealSlot: String? = nil,
        originalUserText: String? = nil,
        confirmed: Bool = true,
        items: [MealEntryItem] = []
    ) {
        self.timestamp = timestamp
        self.dayKey = dayKey
        self.mealSlot = mealSlot
        self.originalUserText = originalUserText
        self.confirmed = confirmed
        self.items = items
    }

    var calories: Double { items.reduce(0) { $0 + $1.calories } }
    var proteinG: Double { items.reduce(0) { $0 + $1.proteinG } }
    var carbsG: Double { items.reduce(0) { $0 + $1.carbsG } }
    var fatG: Double { items.reduce(0) { $0 + $1.fatG } }
}

@Model
final class MealEntryItem {
    var name: String
    var grams: Double
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    /// Catalog food id when known (variety / corrections).
    var foodId: String = ""
    /// Ingredient family snapshot for same-day variety hard filter.
    var ingredientFamily: String = ""
    /// catalog, usda, usda_branded, web, estimate, or diary.
    var source: String = ""
    var entry: MealEntry?

    init(
        name: String,
        grams: Double,
        calories: Double,
        proteinG: Double,
        carbsG: Double,
        fatG: Double,
        foodId: String = "",
        ingredientFamily: String = "",
        source: String = ""
    ) {
        self.name = name
        self.grams = grams
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.foodId = foodId
        self.ingredientFamily = ingredientFamily
        self.source = source
    }
}

@Model
final class LibraryItem {
    var name: String
    var kindRaw: String
    var originRaw: String
    var detail: String
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    var createdAt: Date

    var kind: LibraryKind {
        get { LibraryKind(rawValue: kindRaw) ?? .meal }
        set { kindRaw = newValue.rawValue }
    }

    var origin: LibraryOrigin {
        get { LibraryOrigin(rawValue: originRaw) ?? .user }
        set { originRaw = newValue.rawValue }
    }

    init(
        name: String,
        kind: LibraryKind,
        origin: LibraryOrigin,
        detail: String = "",
        calories: Double = 0,
        proteinG: Double = 0,
        carbsG: Double = 0,
        fatG: Double = 0,
        createdAt: Date = .now
    ) {
        self.name = name
        self.kindRaw = kind.rawValue
        self.originRaw = origin.rawValue
        self.detail = detail
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.createdAt = createdAt
    }
}

enum LibraryKind: String, Codable, CaseIterable, Identifiable {
    case meal
    case recipe
    case food

    var id: String { rawValue }

    var title: String {
        switch self {
        case .meal: "Meals"
        case .recipe: "Recipes"
        case .food: "Foods"
        }
    }
}

enum LibraryOrigin: String, Codable, CaseIterable {
    case user
    case aiGenerated

    var title: String {
        switch self {
        case .user: "Yours"
        case .aiGenerated: "AI-generated"
        }
    }
}

enum DayKey {
    static func make(from date: Date = .now, calendar: Calendar = .current) -> String {
        let comps = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", comps.year ?? 0, comps.month ?? 0, comps.day ?? 0)
    }

    static func date(from key: String, calendar: Calendar = .current) -> Date? {
        let parts = key.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
    }
}
