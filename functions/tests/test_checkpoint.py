from agent.graph import get_graph, reset_graph, run_interpret
from agent.harness.checkpointer import get_checkpointer
from agent.harness.mock_turn import push_mock_turns


def setup_function(_fn):
    reset_graph()


def _payload(utterance):
    return {
        "utterance": utterance,
        "timezone": "UTC",
        "dayKey": "2026-10-13",
        "preferenceContext": {"likes": [], "dislikes": [], "allergies": [], "diets": []},
        "diaryContext": {
            "today": [],
            "previousDays": [],
            "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
        },
        "longTermMemory": [],
        "conversation": {"threadId": "t1", "summary": "", "recentTurns": [], "workingMemory": None},
        "context": {"assistanceLevel": "fullAssist", "lastIntent": None},
    }


def test_two_invokes_on_same_thread_checkpoint():
    push_mock_turns(
        [
            {"kind": "text", "text": "Hello."},
            {"kind": "text", "text": "What is left?"},
        ]
    )
    first = run_interpret(_payload("Hey"), uid="u1", thread_id="t1")
    assert first["assistantMessage"] == "Hello."
    second = run_interpret(_payload("what is left"), uid="u1", thread_id="t1")
    assert second["assistantMessage"] == "What is left?"
    saver = get_checkpointer()
    config = {"configurable": {"thread_id": "u1:t1"}}
    listed = list(saver.list(config))
    assert len(listed) >= 2
