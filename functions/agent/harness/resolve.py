"""Deterministic food resolve: catalog/USDA search, portion, queue."""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from agent.harness.portions import resolve_portion
from schemas import (
    ClarifyOption,
    CommittedFood,
    HouseholdMeasure,
    ItemDraft,
    MacroTotals,
    ResolvedItem,
    ResolveQueue,
)

CANONICAL_SOURCES = {"catalog", "usda", "usda_branded", "web", "estimate", "diary"}


def canonical_source(source: str | None) -> str:
    value = (source or "").strip().lower()
    if value in {"seed", "catalog"}:
        return "catalog"
    if value in CANONICAL_SOURCES:
        return value
    return "catalog"


def singularize(text: str) -> str:
    parts = (text or "").split()
    if not parts:
        return text
    last = parts[-1]
    low = last.lower()
    if len(low) > 3 and low.endswith("s") and not low.endswith("ss"):
        parts[-1] = last[:-1]
        return " ".join(parts)
    return text


def query_list(draft: ItemDraft) -> list[str]:
    queries: list[str] = []

    def add(value: str | None) -> None:
        text = " ".join((value or "").split()).strip()
        if not text:
            return
        if text.lower() in {q.lower() for q in queries}:
            return
        queries.append(text)

    add(draft.foodQuery)
    if draft.brandOrVenue:
        add(f"{draft.brandOrVenue} {draft.foodQuery}")
    for alias in draft.aliases or []:
        add(alias)
    add(singularize(draft.foodQuery))
    return queries[:5]


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.strip().lower().encode()).hexdigest()[:10]
    return f"{prefix}{digest}"


def _macros(value: Any) -> Optional[MacroTotals]:
    if isinstance(value, MacroTotals):
        return value
    if isinstance(value, dict):
        try:
            return MacroTotals.model_validate(value)
        except Exception:  # noqa: BLE001
            return None
    return None


def _measures(value: Any) -> list[HouseholdMeasure]:
    out: list[HouseholdMeasure] = []
    for raw in value or []:
        if isinstance(raw, HouseholdMeasure):
            out.append(raw)
            continue
        if isinstance(raw, dict):
            try:
                out.append(HouseholdMeasure.model_validate(raw))
            except Exception:  # noqa: BLE001
                continue
    return out


@dataclass
class ItemResult:
    draft: ItemDraft
    status: str  # resolved | clarify_food | clarify_portion
    item: Optional[ResolvedItem] = None
    committed: Optional[CommittedFood] = None
    options: list[ClarifyOption] = field(default_factory=list)
    reason: str = ""
    free_text: bool = False
    manual_log: bool = False


def _as_draft(raw: ItemDraft | dict[str, Any]) -> ItemDraft:
    if isinstance(raw, ItemDraft):
        return raw
    return ItemDraft.model_validate(raw)


def _option_from_hit(index: int, hit: dict[str, Any]) -> Optional[ClarifyOption]:
    per = _macros(hit.get("per100g"))
    food_id = str(hit.get("foodId") or "")
    name = str(hit.get("displayName") or "").strip()
    if not food_id or not name or per is None:
        return None
    return ClarifyOption(
        id=f"c{index}",
        label=name,
        foodId=food_id,
        per100g=per,
        source=canonical_source(str(hit.get("source") or "")),
        family=str(hit.get("family") or ""),
        measures=_measures(hit.get("measures")),
    )


def _committed_from_hit(hit: dict[str, Any], measures: list[HouseholdMeasure]) -> Optional[CommittedFood]:
    per = _macros(hit.get("per100g"))
    food_id = str(hit.get("foodId") or "")
    name = str(hit.get("displayName") or "").strip()
    if not food_id or not name or per is None:
        return None
    return CommittedFood(
        foodId=food_id,
        displayName=name,
        per100g=per,
        source=canonical_source(str(hit.get("source") or "")),
        family=str(hit.get("family") or ""),
        citationUrl=hit.get("citationUrl"),
        measures=measures,
    )


def _resolved_from_committed(
    committed: CommittedFood,
    grams: float,
    label: str | None,
) -> ResolvedItem:
    return ResolvedItem(
        foodId=committed.foodId,
        displayName=committed.displayName,
        grams=round(float(grams), 2),
        per100g=committed.per100g,
        source=committed.source,
        citationUrl=committed.citationUrl,
        portionLabel=label,
        family=committed.family,
        measures=list(committed.measures),
    )


def _portion_options(committed: CommittedFood, chips: list[HouseholdMeasure]) -> list[ClarifyOption]:
    options: list[ClarifyOption] = []
    for index, measure in enumerate(chips):
        options.append(
            ClarifyOption(
                id=f"p{index}",
                label=f"{measure.label} ({measure.grams:g} g)",
                foodId=committed.foodId,
                grams=float(measure.grams),
                per100g=committed.per100g,
                source=committed.source,
                family=committed.family,
                citationUrl=committed.citationUrl,
            )
        )
    return options


def _apply_portion(
    draft: ItemDraft,
    committed: CommittedFood,
) -> ItemResult:
    decision = resolve_portion(draft.quantity, draft.unit, committed.measures)
    if decision.grams is not None and decision.grams > 0:
        return ItemResult(
            draft=draft,
            status="resolved",
            item=_resolved_from_committed(committed, decision.grams, decision.label),
            committed=committed,
        )
    return ItemResult(
        draft=draft,
        status="clarify_portion",
        committed=committed,
        options=_portion_options(committed, decision.chips),
        reason="need_amount",
        free_text=decision.free_text or not decision.chips,
    )


def _load_measures(hit: dict[str, Any], fetch_measures: Callable[[str], list[Any]]) -> list[HouseholdMeasure]:
    measures = _measures(hit.get("measures"))
    if measures:
        return measures
    food_id = str(hit.get("foodId") or "")
    if not food_id.startswith("usda_"):
        return []
    try:
        fetched = fetch_measures(food_id)
    except Exception:  # noqa: BLE001
        return []
    return _measures(fetched)


def resolve_one(
    draft: ItemDraft,
    *,
    search: Callable[[str], dict[str, Any]],
    fetch_measures: Callable[[str], list[Any]],
    clock: Callable[[], float],
    deadline: float,
) -> ItemResult:
    if clock() > deadline:
        return ItemResult(draft=draft, status="clarify_food", reason="deadline", manual_log=True, free_text=True)

    queries = query_list(draft) or [draft.foodQuery]
    last_medium: list[dict[str, Any]] = []
    for query in queries:
        if clock() > deadline:
            return ItemResult(draft=draft, status="clarify_food", reason="deadline", manual_log=True, free_text=True)
        try:
            found = search(query) or {}
        except Exception:  # noqa: BLE001
            found = {}
        confidence = str(found.get("confidence") or "none")
        results = list(found.get("results") or [])
        clarify = list(found.get("candidatesForClarify") or results)
        if confidence == "high" and results:
            hit = results[0]
            measures = _load_measures(hit, fetch_measures)
            hit = {**hit, "measures": [m.model_dump() for m in measures]}
            committed = _committed_from_hit(hit, measures)
            if committed is None:
                continue
            return _apply_portion(draft, committed)
        if confidence == "medium" and len(clarify) >= 2:
            last_medium = clarify[:3]
            break
        if confidence == "medium" and len(clarify) == 1:
            hit = clarify[0]
            measures = _load_measures(hit, fetch_measures)
            committed = _committed_from_hit({**hit, "measures": measures}, measures)
            if committed is not None:
                return _apply_portion(draft, committed)

    if last_medium:
        options = [opt for i, hit in enumerate(last_medium) if (opt := _option_from_hit(i, hit))]
        if len(options) >= 2:
            return ItemResult(
                draft=draft,
                status="clarify_food",
                options=options[:3],
                reason="ambiguous",
            )

    if clock() > deadline:
        return ItemResult(draft=draft, status="clarify_food", reason="deadline", manual_log=True, free_text=True)

    return ItemResult(
        draft=draft,
        status="clarify_food",
        reason="not_found",
        manual_log=True,
        free_text=True,
    )


def pick_for_suggestion(result: ItemResult) -> Optional[ResolvedItem]:
    """Suggestions are not HITL — take the top candidate instead of pausing."""
    if result.item is not None:
        return result.item
    committed = result.committed
    if committed is None:
        for option in result.options:
            if not option.foodId or option.per100g is None:
                continue
            committed = CommittedFood(
                foodId=option.foodId,
                displayName=option.label,
                per100g=option.per100g,
                source=canonical_source(option.source),
                family=option.family or "",
                citationUrl=option.citationUrl,
                measures=list(option.measures or []),
            )
            break
    if committed is None:
        return None
    if result.status == "clarify_portion":
        for option in result.options:
            if option.grams:
                return _resolved_from_committed(committed, float(option.grams), option.label)
    applied = _apply_portion(result.draft, committed)
    return applied.item


def resolve_many(
    drafts: list[ItemDraft | dict[str, Any]],
    *,
    search: Callable[[str], dict[str, Any]],
    fetch_measures: Callable[[str], list[Any]],
    clock: Callable[[], float],
    deadline: float,
) -> list[ItemResult]:
    items = [_as_draft(raw) for raw in drafts]
    if not items:
        return []

    def run(draft: ItemDraft) -> ItemResult:
        return resolve_one(
            draft,
            search=search,
            fetch_measures=fetch_measures,
            clock=clock,
            deadline=deadline,
        )

    if len(items) == 1:
        return [run(items[0])]

    results: list[Optional[ItemResult]] = [None] * len(items)
    workers = min(4, len(items))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, draft): index for index, draft in enumerate(items)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [item for item in results if item is not None]


def queue_from_results(results: list[ItemResult]) -> tuple[list[ResolvedItem], Optional[ItemResult], list[ItemDraft]]:
    """Keep resolutions up to the first item that still needs the user."""
    resolved: list[ResolvedItem] = []
    for index, result in enumerate(results):
        if result.status == "resolved" and result.item is not None:
            resolved.append(result.item)
            continue
        remaining = [later.draft for later in results[index + 1 :]]
        return resolved, result, remaining
    return resolved, None, []


def queue_model(
    resolved: list[ResolvedItem],
    paused: Optional[ItemResult],
    remaining: list[ItemDraft],
) -> Optional[ResolveQueue]:
    if paused is None:
        return None
    return ResolveQueue(
        resolved=resolved,
        pending=paused.draft,
        remaining=remaining,
        committed=paused.committed,
        clarifyOptions=paused.options,
    )


def food_query_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]
