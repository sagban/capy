"""Resolve pipeline: confidence, deadline, queue."""

from schemas import ItemDraft, MacroTotals

from agent.harness.deps import set_overrides
from agent.harness.resolve import pick_for_suggestion, query_list, resolve_many


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
    def search(_q, **_kwargs):
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


def test_cited_portion_macros_skip_search():
    def search(_q, **_kwargs):
        raise AssertionError("search should not run when portionMacros are cited")

    # Menu: 12 fl oz latte = 150 kcal (Atwater-consistent).
    results = resolve_many(
        [
            ItemDraft(
                foodQuery="iced latte",
                brandOrVenue="First Cup Coffee",
                quantity=12,
                unit="fl oz",
                portionMacros=MacroTotals(calories=150, proteinG=8, carbsG=18, fatG=5),
                citationUrl="https://example.com/menu",
                displayName="Iced Latte",
            )
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    item = pick_for_suggestion(results[0])
    assert item is not None
    assert item.source == "web"
    assert item.displayName == "Iced Latte"
    assert item.citationUrl == "https://example.com/menu"
    assert abs(item.grams - 12 * 29.5735295625) < 0.5  # US fl oz ≈ g water
    # Stored density is per 100 g derived from the portion.
    scaled = item.per100g.calories * item.grams / 100.0
    assert abs(scaled - 150) < 1.0


def test_cited_menu_unit_sandwich_uses_serving_baseline():
    """Model often says unit=sandwich/order — must not drop when portionMacros are present."""

    def search(_q, **_kwargs):
        raise AssertionError("search should not run")

    results = resolve_many(
        [
            ItemDraft(
                foodQuery="Spinach Feta Sandwich",
                brandOrVenue="First Cup Coffee",
                quantity=1,
                unit="sandwich",
                portionMacros=MacroTotals(calories=290, proteinG=19, carbsG=34, fatG=8),
                citationUrl="https://toast.app",
                displayName="Spinach Feta & Egg White Sandwich",
            )
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    item = pick_for_suggestion(results[0])
    assert item is not None
    assert item.source == "web"
    assert item.grams == 180
    assert abs(item.per100g.calories - 290 * 100 / 180) < 0.5


def test_cited_slice_uses_plate_baseline_not_100g():
    def search(_q, **_kwargs):
        raise AssertionError("search should not run")

    results = resolve_many(
        [
            ItemDraft(
                foodQuery="quiche",
                brandOrVenue="First Cup Coffee",
                quantity=1,
                unit="slice",
                portionMacros=MacroTotals(calories=420, proteinG=18, carbsG=28, fatG=26),
                citationUrl="https://toast.app",
                displayName="Quiche",
            )
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    item = pick_for_suggestion(results[0])
    assert item is not None
    assert item.grams == 150
    assert abs(item.per100g.calories * item.grams / 100.0 - 420) < 1.0


def test_cited_venue_serving_uses_plate_baseline():
    def search(_q, **_kwargs):
        raise AssertionError("search should not run")

    results = resolve_many(
        [
            ItemDraft(
                foodQuery="quiche",
                brandOrVenue="First Cup Coffee",
                quantity=1,
                unit="serving",
                portionMacros=MacroTotals(calories=420, proteinG=18, carbsG=28, fatG=26),
                citationUrl="https://toast.app",
                displayName="Quiche",
            )
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    item = pick_for_suggestion(results[0])
    assert item is not None
    assert item.grams == 180


def test_venue_without_citation_skips_usda_and_fails_fast():
    seen: list[bool] = []

    def search(_q, *, include_usda: bool = True, **_kwargs):
        seen.append(include_usda)
        return {"results": [], "candidatesForClarify": [], "confidence": "none"}

    results = resolve_many(
        [
            ItemDraft(
                foodQuery="avocado toast",
                brandOrVenue="First Cup Coffee",
                quantity=1,
                unit="serving",
            )
        ],
        search=search,
        fetch_measures=lambda _fid: [],
        clock=lambda: 0,
        deadline=45,
    )
    assert results[0].reason == "venue_needs_citation"
    assert seen
    assert all(flag is False for flag in seen)


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
