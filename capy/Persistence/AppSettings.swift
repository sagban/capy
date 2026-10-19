import Foundation
import SwiftData

@Model
final class AppSettings {
    var onboardingCompleted: Bool
    var assistanceLevelRaw: String
    var responseStyleRaw: String = ResponseStyle.balanced.rawValue
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

    var responseStyle: ResponseStyle {
        get { ResponseStyle(rawValue: responseStyleRaw) ?? .balanced }
        set { responseStyleRaw = newValue.rawValue }
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
        responseStyle: ResponseStyle = .balanced,
        guidedCheckInHour: Int = 18,
        guidedCheckInMinute: Int = 0,
        energyUnit: EnergyUnit = .kcal,
        foodMassUnit: FoodMassUnit = .gram,
        bodyMassUnit: BodyMassUnit = .kilogram,
        weekStart: WeekStartPreference = .system
    ) {
        self.onboardingCompleted = onboardingCompleted
        self.assistanceLevelRaw = assistanceLevel.rawValue
        self.responseStyleRaw = responseStyle.rawValue
        self.guidedCheckInHour = guidedCheckInHour
        self.guidedCheckInMinute = guidedCheckInMinute
        self.energyUnitRaw = energyUnit.rawValue
        self.foodMassUnitRaw = foodMassUnit.rawValue
        self.bodyMassUnitRaw = bodyMassUnit.rawValue
        self.weekStartRaw = weekStart.rawValue
    }
}
