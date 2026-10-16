"""Diet constraints for suggestions. Code enforces them; the model does not."""

from __future__ import annotations

import re
from typing import Iterable

from schemas import InterpretMealRequest, MemoryProposal

_MEAT_FAMILIES = frozenset({"poultry", "beef", "pork", "lamb", "meat", "game"})
_FISH_FAMILIES = frozenset({"fish", "seafood", "shellfish"})
_EGG_FAMILIES = frozenset({"egg"})
_DAIRY_FAMILIES = frozenset({"dairy"})

_MEAT_TOKENS = frozenset(
    {
        "chicken",
        "turkey",
        "beef",
        "pork",
        "lamb",
        "bacon",
        "ham",
        "sausage",
        "steak",
        "meat",
        "meats",
        "pepperoni",
        "prosciutto",
        "gelatin",
        "lard",
        "duck",
        "goat",
        "wings",
    }
)
_FISH_TOKENS = frozenset(
    {
        "salmon",
        "tuna",
        "fish",
        "cod",
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "anchovy",
        "sardine",
        "tilapia",
        "trout",
        "mackerel",
        "scallop",
        "clam",
        "oyster",
        "mussel",
        "seafood",
    }
)
_EGG_TOKENS = frozenset({"egg", "eggs"})
_DAIRY_TOKENS = frozenset(
    {"milk", "cheese", "yogurt", "yoghurt", "butter", "cream", "whey", "paneer", "ghee"}
)

_DIET_KEYS = (
    ("vegan", ("vegan",)),
    ("vegetarian", ("vegetarian", "veggie")),
    ("pescatarian", ("pescatarian", "pescetarian")),
    ("dairy-free", ("dairy-free", "dairy free", "nondairy", "non-dairy")),
)


def diets_from_text(text: str) -> list[str]:
    blob = " ".join((text or "").lower().split())
    if not blob:
        return []
    found: list[str] = []
    if re.search(r"\bnot\s+(a\s+)?vegan\b", blob) or re.search(r"\bnot\s+(a\s+)?vegetarian\b", blob):
        pass
    else:
        for key, needles in _DIET_KEYS:
            if any(needle in blob for needle in needles):
                found.append(key)
    return found


def diets_for(req: InterpretMealRequest, proposals: Iterable[MemoryProposal] | None = None) -> list[str]:
    texts: list[str] = []
    texts.extend(req.preferenceContext.diets or [])
    texts.extend(note.text for note in (req.longTermMemory or []) if note.text)
    texts.append(req.utterance or "")
    for turn in req.conversation.recentTurns or []:
        if (turn.role or "") == "user":
            texts.append(turn.text or "")
    for proposal in proposals or []:
        if proposal.text:
            texts.append(proposal.text)
    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        for diet in diets_from_text(text):
            if diet not in seen:
                seen.add(diet)
                out.append(diet)
    return out


def _blocked(diets: list[str]) -> tuple[set[str], set[str]]:
    families: set[str] = set()
    tokens: set[str] = set()
    labels = set(diets)
    if "vegan" in labels or "vegetarian" in labels:
        families |= _MEAT_FAMILIES | _FISH_FAMILIES
        tokens |= _MEAT_TOKENS | _FISH_TOKENS
    if "vegan" in labels:
        families |= _EGG_FAMILIES | _DAIRY_FAMILIES
        tokens |= _EGG_TOKENS | _DAIRY_TOKENS
    if "pescatarian" in labels:
        families |= _MEAT_FAMILIES
        tokens |= _MEAT_TOKENS
    if "dairy-free" in labels:
        families |= _DAIRY_FAMILIES
        tokens |= _DAIRY_TOKENS
    return families, tokens


def item_breaks_diet(name: str, family: str, diets: list[str]) -> bool:
    if not diets:
        return False
    families, tokens = _blocked(diets)
    fam = (family or "").strip().lower()
    if fam and fam in families:
        return True
    words = set(re.findall(r"[a-z0-9]+", (name or "").lower()))
    return bool(words & tokens)
