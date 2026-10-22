"""Strict library matching — no staple overfit."""

from agent.tools.search.library_match import library_name_match, match_library
from schemas import LibraryItemRef


def _item(name: str, item_id: str = "1") -> LibraryItemRef:
    return LibraryItemRef(
        id=item_id,
        name=name,
        kind="meal",
        calories=500,
        proteinG=40,
        carbsG=40,
        fatG=15,
        servingGrams=400,
    )


def test_exact_title_matches():
    assert library_name_match("Gym Bowl", "Gym Bowl")
    assert library_name_match("gym bowl", "Gym Bowl")


def test_broad_staple_does_not_match_multiword_library():
    assert not library_name_match("chicken", "Sunday Chicken Feast")
    assert not library_name_match("rice", "Leftover Rice Bowl")


def test_user_names_library_title_tokens():
    assert library_name_match("gym bowl", "Gym Bowl")
    hits = match_library("Gym Bowl", [_item("Gym Bowl"), _item("Sunday Chicken Feast", "2")])
    assert len(hits) == 1
    assert hits[0].source == "library"
    assert hits[0].foodId == "library_1"
