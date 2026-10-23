"""Firebase callable Int64 wrappers must not fail profile or diary reads."""

from schemas import MacroTotals, normalize_firebase_payload


def _int64(value: str) -> dict:
    return {"@type": "type.googleapis.com/google.protobuf.Int64Value", "value": value}


def test_normalize_unwraps_daily_target_int64_wrappers():
    raw = {
        "dailyTarget": {
            "calories": _int64("2000"),
            "proteinG": _int64("150"),
            "carbsG": _int64("200"),
            "fatG": _int64("67"),
        }
    }
    cleaned = normalize_firebase_payload(raw)
    target = MacroTotals.model_validate(cleaned["dailyTarget"])
    assert target.calories == 2000
    assert target.proteinG == 150
    assert target.carbsG == 200
    assert target.fatG == 67
