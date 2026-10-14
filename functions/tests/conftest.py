import os

import pytest

# Offline stand-in — never hit live Vertex in unit tests.
os.environ.setdefault("CAPY_MOCK_AGENT", "1")


@pytest.fixture(autouse=True)
def _reset_harness_state():
    from harness.deps import clear_overrides
    from harness.mock_turn import clear_mock_turns

    clear_overrides()
    clear_mock_turns()
    yield
    clear_overrides()
    clear_mock_turns()
