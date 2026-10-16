"""Resolve pipeline: confidence, deadline, queue."""

from schemas import ItemDraft

from agent.harness.deps import set_overrides
from agent.harness.resolve import query_list, resolve_many


def _clock_factory(values):
    seq = iter(values)

    def clock():
        return next(seq)

    return clock


def _hit(name, food_id, confidence, measures=None, extra=None):
    row = {
        "foodId": food_id,
        "displayName": name,
        "source": "seed",
        "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
        "family": "egg",
        "measures": measures or [],
    }
    if extra:
        row.update(extra)
    packed = {
        "results": [row] if confidence == "high" else [],
        "candidatesForClarify": [row] if confidence != "none" else [],
        "confidence": confidence,
    }
    return packed


def test_query_list_brand_alias_singular_capped():
    draft = ItemDraft(
        foodQuery="eggs",
        brandOrVenue="Vital Farms",
        aliases=["hen egg", "whole egg"],
    )
    queries = query_list(draft)
    assert queries[0] == "eggs"
    assert "Vital Farms eggs" in queries
    assert "egg" in queries
    assert len(queries) <= 5


def test_high_commits_with_portion():
    def search(_q):
        return _hit("Egg", "seed_egg", "high", [{"id": "m0", "label": "1 large", "grams": 50}])

    results = resolve_many(
        [ItemDraft(foodQuery="egg", quantity=2, unit="large")],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    assert results[0].status == "resolved"
    assert results[0].item is not None
    assert results[0].item.grams == 100
    assert results[0].item.source == "catalog"


def test_medium_clarifies_top_candidates():
    def search(_q):
        a = _hit("Chicken sandwich A", "usda_1", "medium")["candidatesForClarify"][0]
        b = {**a, "foodId": "usda_2", "displayName": "Chicken sandwich B"}
        return {
            "results": [],
            "candidatesForClarify": [a, b],
            "confidence": "medium",
        }

    results = resolve_many(
        [ItemDraft(foodQuery="chicken sandwich")],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    assert results[0].status == "clarify_food"
    assert len(results[0].options) == 2


def test_search_miss_clarifies_with_manual_log():
    def search(_q):
        return {"results": [], "candidatesForClarify": [], "confidence": "none"}

    missed = resolve_many(
        [ItemDraft(foodQuery="mystery foam")],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    assert missed[0].status == "clarify_food"
    assert missed[0].reason == "not_found"
    assert missed[0].manual_log is True


def test_deadline_pauses_as_clarify():
    calls = {"n": 0}

    def clock():
        calls["n"] += 1
        return 0 if calls["n"] == 1 else 100

    # resolve_many does not add the deadline; the caller does. Mirror execute: deadline = first clock + 45
    # Here we pass deadline 10 and a clock that is already past it.
    results = resolve_many(
        [ItemDraft(foodQuery="egg")],
        search=lambda _q: (_ for _ in ()).throw(AssertionError("search")),
        fetch_measures=lambda _fid: [],
        clock=lambda: 100,
        deadline=10,
    )
    assert results[0].reason == "deadline"
    assert clock  # silence unused in this direct-deadline case


def test_queue_pauses_on_first_clarify_and_keeps_later_drafts():
    def search(query):
        if "egg" in query:
            return _hit("Egg", "seed_egg", "high", [{"id": "m0", "label": "1 large", "grams": 50}])
        a = _hit("Chicken A", "usda_1", "medium")["candidatesForClarify"][0]
        b = {**a, "foodId": "usda_2", "displayName": "Chicken B"}
        return {"results": [], "candidatesForClarify": [a, b], "confidence": "medium"}

    from agent.harness.resolve import queue_from_results

    results = resolve_many(
        [
            ItemDraft(foodQuery="egg", quantity=1, unit="large"),
            ItemDraft(foodQuery="chicken sandwich"),
            ItemDraft(foodQuery="rice", quantity=100, unit="g"),
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    resolved, paused, remaining = queue_from_results(results)
    assert [item.displayName for item in resolved] == ["Egg"]
    assert paused is not None and paused.status == "clarify_food"
    assert [draft.foodQuery for draft in remaining] == ["rice"]
    set_overrides()  # no-op, keeps import used if a future test needs it
