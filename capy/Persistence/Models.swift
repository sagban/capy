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

    var assistanceLevel: AssistanceLevel {
        get { AssistanceLevel(rawValue: assistanceLevelRaw) ?? .guided }
        set { assistanceLevelRaw = newValue.rawValue }
    }

    init(
        onboardingCompleted: Bool = false,
        assistanceLevel: AssistanceLevel = .fullAssist,
        guidedCheckInHour: Int = 18,
        guidedCheckInMinute: Int = 0
    ) {
        self.onboardingCompleted = onboardingCompleted
        self.assistanceLevelRaw = assistanceLevel.rawValue
        self.guidedCheckInHour = guidedCheckInHour
        self.guidedCheckInMinute = guidedCheckInMinute
    }
}

@Model
final class DailyTarget {
    var effectiveDate: Date
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double

    init(
        effectiveDate: Date = Calendar.current.startOfDay(for: .now),
        calories: Double = 2000,
        proteinG: Double = 140,
        carbsG: Double = 200,
        fatG: Double = 65
    ) {
        self.effectiveDate = effectiveDate
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
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
final class MealEntry {
    var timestamp: Date
    var dayKey: String
    var mealSlot: String?
    var originalUserText: String?
    var confirmed: Bool
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
    var entry: MealEntry?

    init(
        name: String,
        grams: Double,
        calories: Double,
        proteinG: Double,
        carbsG: Double,
        fatG: Double
    ) {
        self.name = name
        self.grams = grams
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
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
