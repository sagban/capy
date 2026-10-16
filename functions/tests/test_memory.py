from agent.harness.memory.assemble import build_pack
from schemas import request_from_dict


def test_context_pack_has_memory_layers():
    req = request_from_dict(
        {
            "utterance": "what is left",
            "dayKey": "2026-10-13",
            "timezone": "UTC",
            "preferenceContext": {
                "likes": ["eggs"],
                "dislikes": [],
                "allergies": ["peanut"],
                "diets": ["vegetarian"],
            },
            "diaryContext": {
                "today": [],
                "previousDays": [],
                "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
            },
            "longTermMemory": [{"id": "n1", "text": "no microwave"}],
            "conversation": {
                "threadId": "default",
                "summary": "",
                "recentTurns": [{"role": "user", "text": "hi"}],
                "workingMemory": None,
            },
        }
    )
    pack = build_pack(req)
    assert '"episodic"' in pack
    assert '"semantic"' in pack
    assert '"longTerm"' in pack
    assert "no microwave" in pack
    assert "peanut" in pack
    assert "slotBudgets" in pack
    assert "recentTurns" in pack
