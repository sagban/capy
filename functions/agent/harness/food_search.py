"""Multi-source food search ranking — correct log > any hit.

Inspired by fielded BM25 (BM25F), e-commerce broad/narrow query split, and
nutrition-app personalization (recents / favorites). See
docs/architecture/food-search-ranking.md.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from agent.harness.catalog import search_seed
from schemas import FoodHit, InterpretMealRequest
from agent.harness.usda import search_usda_pool

QueryBreadth = Literal["broad", "narrow"]

_STOP = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "with",
    "in",
    "for",
    "to",
    "my",
    "i",
    "just",
    "had",
    "ate",
    "some",
    "that",
    "this",
    "one",
    "ones",
}
_FORM = {"raw", "cooked", "dry", "dried", "fresh", "frozen", "whole", "plain"}
# Keep "whole" as a content token when paired with these staples (USDA "Egg, whole, …").
_WHOLE_STAPLES = frozenset({"egg", "eggs", "milk", "wheat", "grain", "kernel"})
_NOISE = (
    "babyfood",
    "infant",
    "toddler",
    "alcoholic",
    "imitation",
    "cereals ready-to-eat",
    "snacks,",
    " chips",
    "chip,",
)
# Meal/composite cues — penalize on broad staple queries when the user did not ask for them.
_COMPOSITE = (
    "sandwich",
    "croissant",
    "sausage",
    "burrito",
    "pizza",
    "muffin",
    "cookie",
    "nugget",
    "omelet",
    "omelette",
    "quiche",
    "wrap",
    "biscuit",
)
_CHAINS = (
    "mcdonald",
    "mcdonalds",
    "subway",
    "pizza hut",
    "wendy",
    "wendys",
    "burger king",
    "taco bell",
    "domino",
)


@dataclass
class RankedHit:
    hit: FoodHit
    score: float
    match: float
    personal: float
    penalties: float
    unexplained: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9%]+", text.lower()) if t]


def canonical_staple_query(query: str) -> str:
    """Map common logging phrases to USDA/seed naming (whole egg → egg, whole)."""
    q = (query or "").strip().lower()
    q = re.sub(r"\bwhole\s+eggs?\b", "egg, whole", q)
    q = re.sub(r"\beggs?,\s*whole\b", "egg, whole", q)
    return q


def staple_query_variants(query: str) -> list[str]:
    """Distinct query strings to retrieve seed/USDA pools for staples."""
    raw = (query or "").strip()
    if not raw:
        return []
    seen: list[str] = []
    for candidate in (raw, canonical_staple_query(raw)):
        c = candidate.strip()
        if c and c.lower() not in {s.lower() for s in seen}:
            seen.append(c)
    return seen


def content_tokens(query: str) -> list[str]:
    toks = _tokens(query)
    keep_whole = "whole" in toks and any(t in _WHOLE_STAPLES for t in toks)
    out: list[str] = []
    for t in toks:
        if t in _STOP or len(t) <= 1:
            continue
        if t in _FORM and not (t == "whole" and keep_whole):
            continue
        if t not in out:
            out.append(t)
    # Canonical form also contributes egg+whole coverage for "Egg, whole, …" names.
    canon = canonical_staple_query(query)
    if canon != query.lower().strip():
        for t in _tokens(canon):
            if t in _STOP or len(t) <= 1:
                continue
            if t in _FORM and not (t == "whole" and keep_whole):
                continue
            if t not in out:
                out.append(t)
    return out


def identity_tokens(query: str) -> list[str]:
    """Brand-nickname / ALLCAPS identity tokens (not lone 3-letter staples like 'egg')."""
    words = query.split()
    content = content_tokens(query)
    out: list[str] = []
    for raw in words:
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", raw)
        if not cleaned:
            continue
        t = cleaned.lower()
        if t in _FORM or t in _STOP:
            continue
        shout = raw.isupper() and 2 <= len(cleaned) <= 5
        short = len(t) <= 3
        # Short token is identity only with other content, or when shouted (ON).
        if shout or (short and len(content) >= 1 and t not in content):
            # If the whole query is a single short staple ("egg"), content==[egg] —
            # don't treat it as an unresolved brand nickname.
            if short and content == [t] and not shout:
                continue
            if t not in out:
                out.append(t)
        elif short and len(words) >= 2 and t not in content:
            if t not in out:
                out.append(t)
    return out


def query_breadth(query: str) -> QueryBreadth:
    """E-commerce style: broad category vs narrow product/brand intent."""
    q = query.lower()
    content = content_tokens(query)
    identity = identity_tokens(query)
    if any(c in q for c in _CHAINS):
        return "narrow"
    if identity:
        return "narrow"
    if len(content) >= 3:
        return "narrow"
    words = [w for w in query.split() if w]
    titled = sum(1 for w in words if len(w) > 2 and w[0].isupper())
    if titled >= 2:
        return "narrow"
    # Proper-noun + food word: "Fage yogurt"
    if titled >= 1 and len(content) >= 2:
        return "narrow"
    return "broad"


def _split_fields(display_name: str) -> tuple[str, str]:
    """Split 'DESCRIPTION — Brand Owner' (USDA branding we append)."""
    if " — " in display_name:
        desc, brand = display_name.split(" — ", 1)
        return desc.strip(), brand.strip()
    if " (" in display_name and display_name.endswith(")"):
        # Older "Name (Brand)" shape
        left, _, right = display_name.rpartition(" (")
        return left.strip(), right[:-1].strip()
    return display_name.strip(), ""


def _bm25_field(query_tokens: list[str], field_text: str, *, avgdl: float = 8.0) -> float:
    """BM25-lite on a single field (k1=1.2, b=0.75). Corpus IDF approximated."""
    if not query_tokens or not field_text:
        return 0.0
    k1, b = 1.2, 0.75
    field_tokens = _tokens(field_text)
    if not field_tokens:
        return 0.0
    dl = len(field_tokens)
    tf: dict[str, int] = {}
    for t in field_tokens:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for qt in query_tokens:
        f = tf.get(qt, 0)
        if f <= 0:
            continue
        # Pseudo-IDF: rarer in English-ish → slightly higher; capped.
        idf = math.log(1.0 + 10.0 / (1.0 + len(qt)))
        denom = f + k1 * (1 - b + b * dl / avgdl)
        score += idf * (f * (k1 + 1)) / denom
    return score


def _token_in_text(token: str, text: str) -> bool:
    """Substring OK for len>=3; short tokens need whole-word (avoid hi⊂chicken)."""
    n = text.lower()
    t = token.lower()
    if len(t) >= 3:
        return t in n
    return bool(re.search(rf"(^|[\s,/(-]){re.escape(t)}($|[\s,)/])", n))


def _coverage(tokens: list[str], text: str) -> float:
    if not tokens:
        return 0.0
    return sum(1 for t in tokens if _token_in_text(t, text)) / len(tokens)


def _exactness(name: str, query: str) -> float:
    n = name.lower().strip()
    variants = [query.lower().strip(), canonical_staple_query(query)]
    best = 0.0
    for q in variants:
        if not q:
            continue
        if n == q:
            best = max(best, 1.0)
            continue
        if n.startswith(q + ",") or n.startswith(q + " "):
            best = max(best, 0.9)
            continue
        if n.startswith(q):
            best = max(best, 0.75)
            continue
        # Contiguous phrase in the middle — weak when the title is a multi-ingredient meal.
        if re.search(rf"(^|[\s,/(-]){re.escape(q)}($|[\s,)/&])", n):
            composite_bits = n.count(",") + n.count("&")
            best = max(best, 0.35 if composite_bits >= 2 else 0.7)
    return best


def _personal_score(hit: FoodHit, req: InterpretMealRequest) -> float:
    score = 0.0
    name = hit.displayName.lower()
    fid = hit.foodId

    likes = [x.lower() for x in (req.preferenceContext.likes or [])]
    if any(x and (x in name or name in x) for x in likes):
        score += 14.0

    dislikes = [x.lower() for x in (req.preferenceContext.dislikes or [])]
    if any(x and x in name for x in dislikes):
        score -= 20.0

    for entry in req.diaryContext.today or []:
        en = (entry.name or "").lower()
        if en and (en in name or name in en):
            score += 12.0
            break

    for corr in (req.memorySnapshot.recentCorrections if req.memorySnapshot else []) or []:
        ct = (corr.text or "").lower()
        if not ct:
            continue
        # Prefer hits that share distinctive tokens with the correction text.
        hit_toks = [t for t in _tokens(name) if len(t) > 3]
        overlap = sum(1 for t in hit_toks if t in ct)
        if overlap:
            score += 6.0 + 4.0 * overlap
            break

    wm = req.conversation.workingMemory
    if wm:
        for c in list(wm.candidates or []):
            if c.foodId == fid:
                score += 28.0
            elif (c.displayName or "").lower() and (
                (c.displayName or "").lower() in name or name in (c.displayName or "").lower()
            ):
                score += 14.0
        if wm.pendingAction:
            for c in wm.pendingAction.payload.candidates or []:
                if c.foodId == fid:
                    score += 28.0
    return score


def _item_quality(hit: FoodHit, breadth: QueryBreadth, *, personal: float = 0.0) -> float:
    """Document/item features: trust + completeness; seed bias only for broad queries."""
    q = 0.0
    per = hit.per100g
    if per.calories > 0 and per.proteinG >= 0:
        q += 3.0
    if per.calories > 0 and (per.carbsG > 0 or per.fatG > 0 or per.proteinG > 0):
        q += 2.0
    if breadth == "broad" and hit.source == "seed":
        q += 6.0
    if breadth == "broad" and hit.source == "usda":
        q += 4.0
    if breadth == "broad" and hit.source == "usda_branded":
        # Diary/likes already chose this brand — don't fight personal score.
        if personal <= 0:
            q -= 8.0
    if breadth == "narrow" and hit.source == "usda_branded":
        q += 4.0
    if breadth == "narrow" and hit.source == "seed":
        q += 1.0
    return q


def _penalties(name: str, query: str, unexplained: list[str], breadth: QueryBreadth) -> float:
    n = name.lower()
    p = 0.0
    if any(t in n for t in _NOISE):
        p += 22.0
    q = query.lower()
    chain_asked = any(t in q for t in _CHAINS)
    if any(t in n for t in _CHAINS) and not chain_asked:
        p += 12.0
    # Composite meals on staple queries (whole egg → croissant sandwich).
    # Skip when the user named a chain (mcdonalds chicken sandwich is expected).
    if (
        not chain_asked
        and any(cue in n for cue in _COMPOSITE)
        and not any(cue in q for cue in _COMPOSITE)
    ):
        p += 20.0 if breadth == "broad" else 12.0
    # Unexplained identity/content tokens — wrong product risk.
    weight = 14.0 if breadth == "narrow" else 8.0
    p += weight * len(unexplained)
    return p


def _unexplained(desc: str, brand: str, content: list[str], identity: list[str]) -> list[str]:
    hay = f"{desc} {brand}"
    missing: list[str] = []
    for t in content + identity:
        if not _token_in_text(t, hay) and t not in missing:
            missing.append(t)
    return missing


def score_hit(
    hit: FoodHit,
    query: str,
    req: InterpretMealRequest,
    *,
    breadth: QueryBreadth | None = None,
) -> RankedHit:
    breadth = breadth or query_breadth(query)
    content = content_tokens(query)
    identity = [t for t in identity_tokens(query) if t not in content]
    desc, brand = _split_fields(hit.displayName)

    q_tokens = content + identity
    bm25_desc = _bm25_field(q_tokens, desc)
    bm25_brand = _bm25_field(q_tokens, brand) * 1.35  # brand field weight (BM25F-style)
    exact = _exactness(desc, query)
    cov = _coverage(content, f"{desc} {brand}") if content else exact
    brand_cov = _coverage(q_tokens, brand) if brand else 0.0

    # Lexical match aggregate (0–~50). Coverage weighted higher for multi-token.
    match = (
        18.0 * exact
        + 10.0 * min(bm25_desc, 3.0) / 3.0
        + 12.0 * min(bm25_brand, 3.0) / 3.0
        + 16.0 * cov
        + 10.0 * brand_cov
    )

    personal = _personal_score(hit, req)
    quality = _item_quality(hit, breadth, personal=personal)
    unexplained = _unexplained(desc, brand, content, identity)
    penalties = _penalties(hit.displayName, query, unexplained, breadth)

    # Form: honor raw/cooked intent; otherwise prefer cooked staples on broad queries.
    form = 0.0
    nl = hit.displayName.lower()
    ql = query.lower()
    wants_raw = any(t in ql for t in ("raw", "uncooked"))
    wants_dry = "dry" in ql and "dried" not in nl  # weak
    if wants_raw:
        if ", raw" in nl or " uncooked" in nl or nl.endswith(" raw"):
            form += 8.0
        if "cooked" in nl:
            form -= 6.0
    elif breadth == "broad":
        if "cooked" in nl:
            form += 4.0
        elif ", raw" in nl:
            form -= 3.0
    if wants_dry and ("dry" in nl or "uncooked" in nl):
        form += 3.0

    score = match + personal + quality + form - penalties
    return RankedHit(
        hit=hit,
        score=score,
        match=match,
        personal=personal,
        penalties=penalties,
        unexplained=unexplained,
        features={
            "exact": exact,
            "bm25_desc": bm25_desc,
            "bm25_brand": bm25_brand,
            "coverage": cov,
            "brand_coverage": brand_cov,
            "quality": quality,
            "form": form,
            "breadth_narrow": 1.0 if breadth == "narrow" else 0.0,
        },
    )


def rank_candidates(
    hits: list[FoodHit],
    query: str,
    req: InterpretMealRequest,
) -> list[RankedHit]:
    breadth = query_breadth(query)
    ranked = [score_hit(h, query, req, breadth=breadth) for h in hits]
    ranked.sort(key=lambda r: (-r.score, len(r.hit.displayName), r.hit.displayName.lower()))
    return ranked


def confidence_for(ranked: list[RankedHit], query: str) -> tuple[str, bool, str]:
    breadth = query_breadth(query)
    if not ranked:
        return "none", True, "no_hits"
    top = ranked[0]
    second = ranked[1].score if len(ranked) > 1 else -999.0
    gap = top.score - second
    q = query.strip()

    # Ultra-short queries: only accept strong exact/prefix; else escalate.
    if len(q) < 3 and top.features.get("exact", 0) < 0.7:
        return "low", True, "short_query_weak"

    if top.unexplained:
        return "low", True, "unresolved_query_tokens"
    if top.match < 12.0:
        return "low", True, "weak_name_match"
    if top.score < 14.0:
        return "low", True, "low_score"
    if breadth == "narrow" and top.features.get("coverage", 0) < 0.6 and top.features.get("brand_coverage", 0) < 0.5:
        return "low", True, "narrow_weak_coverage"
    if gap < 2.5 and top.match < 28.0:
        return "medium", True, "ambiguous_top"
    if top.match >= 26.0 and not top.unexplained:
        return "high", False, "strong_match"
    return "medium", False, "usable_match"


# Back-compat name used in older tests.
def _confidence(ranked: list[RankedHit]) -> tuple[str, bool, str]:
    return confidence_for(ranked, query="")


def search_foods(req: InterpretMealRequest, query: str, limit: int = 8) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "results": [],
            "candidatesForClarify": [],
            "weakHints": [],
            "confidence": "none",
            "suggestWebSearch": True,
            "reason": "empty_query",
            "sources": [],
            "cache": "miss",
            "queryBreadth": "broad",
        }

    breadth = query_breadth(q)
    variants = staple_query_variants(q)
    seed_hits: list[FoodHit] = []
    usda_hits: list[FoodHit] = []
    for variant in variants:
        seed_hits.extend(search_seed(variant, limit=max(12, limit)))
        usda_hits.extend(search_usda_pool(variant, limit=max(30, limit * 4)))

    merged: dict[str, FoodHit] = {}
    for h in seed_hits + usda_hits:
        if h.foodId not in merged:
            merged[h.foodId] = h

    ranked = rank_candidates(list(merged.values()), q, req)

    diets = {d.lower() for d in req.preferenceContext.diets or []}
    if "vegetarian" in diets or "vegan" in diets:
        blocked = {"poultry", "fish", "meat", "beef", "pork"}
        if "vegan" in diets:
            blocked |= {"dairy", "egg"}
        ranked = [r for r in ranked if r.hit.family.lower() not in blocked]

    confidence, suggest_web, reason = confidence_for(ranked, q)
    top = ranked[:limit]
    packed = [
        {
            "foodId": r.hit.foodId,
            "displayName": r.hit.displayName,
            "source": r.hit.source,
            "per100g": r.hit.per100g.model_dump(),
            "family": r.hit.family,
            "measures": [m.model_dump() for m in (r.hit.measures or [])],
            "score": round(r.score, 2),
            "unexplainedTokens": r.unexplained,
            "features": {k: round(v, 3) for k, v in r.features.items()},
        }
        for r in top
    ]

    results = [] if confidence == "low" else packed
    cache = "hit" if seed_hits else ("usda" if usda_hits else "miss")
    sources: list[str] = []
    if seed_hits:
        sources.append("seed")
    if any(h.source == "usda_branded" for h in usda_hits):
        sources.append("usda_branded")
    if any(h.source == "usda" for h in usda_hits):
        sources.append("usda")

    return {
        "results": results,
        "candidatesForClarify": packed[:5],
        "weakHints": [p["displayName"] for p in packed[:3]] if confidence == "low" else [],
        "cache": cache,
        "confidence": confidence,
        "suggestWebSearch": suggest_web,
        "reason": reason,
        "sources": sources,
        "queryBreadth": breadth,
    }
