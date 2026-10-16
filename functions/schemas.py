"""Pydantic DTOs mirroring docs/architecture/api-contracts.md."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class MealIntent(str, Enum):
    log_meal = "log_meal"
    suggest_meal = "suggest_meal"
    correct_meal = "correct_meal"
    clarify = "clarify"
    update_preference = "update_preference"
    update_memory = "update_memory"
    unknown = "unknown"


class PendingActionType(str, Enum):
    clarify_portion = "clarify_portion"
    clarify_food = "clarify_food"
    confirm_log = "confirm_log"
    confirm_correction = "confirm_correction"
    confirm_delete = "confirm_delete"


class MacroTotals(BaseModel):
    calories: float
    proteinG: float
    carbsG: float
    fatG: float


class PreferenceContext(BaseModel):
    likes: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    diets: list[str] = Field(default_factory=list)


class DiaryEntry(BaseModel):
    name: str
    mealSlot: Optional[str] = None
    grams: Optional[float] = None
    entryId: Optional[str] = None
    itemIndex: Optional[int] = None
    foodId: Optional[str] = None
    source: Optional[str] = None
    per100g: Optional[MacroTotals] = None
    ingredientFamily: Optional[str] = None


class DiaryDayEntry(DiaryEntry):
    """Same shape as today; kept so older call sites stay valid."""


class DiaryDaySummary(BaseModel):
    dayKey: str
    mealCount: int
    itemNames: list[str] = Field(default_factory=list)
    entries: list[DiaryDayEntry] = Field(default_factory=list)


class MealPlanSlot(BaseModel):
    """User meal plan for the day (e.g. Meal 1…Meal 6). Order is sortOrder, not a fixed name list."""

    name: str
    sortOrder: int = 0
    enabled: bool = True


class DiaryContext(BaseModel):
    today: list[DiaryEntry] = Field(default_factory=list)
    previousDays: list[DiaryDaySummary] = Field(default_factory=list)
    remaining: MacroTotals
    remainingSource: str = "clientComputed"
    mealPlan: list[MealPlanSlot] = Field(default_factory=list)


class LongTermMemoryNote(BaseModel):
    id: str
    text: str


class ConversationTurn(BaseModel):
    role: str
    text: str


class HouseholdMeasure(BaseModel):
    id: str
    label: str
    grams: float


class WorkingMemoryCandidate(BaseModel):
    foodId: str
    displayName: str
    grams: Optional[float] = None
    source: Optional[str] = None


class ItemDraft(BaseModel):
    rawText: str = ""
    foodQuery: str
    brandOrVenue: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    aliases: list[str] = Field(default_factory=list, description="Other names to search.")


class ResolvedItem(BaseModel):
    foodId: str
    displayName: str
    grams: float
    per100g: MacroTotals
    source: str
    citationUrl: Optional[str] = None
    portionLabel: Optional[str] = None
    family: str = ""
    measures: list[HouseholdMeasure] = Field(default_factory=list)
    entryId: Optional[str] = None
    itemIndex: Optional[int] = None


class ClarifyOption(BaseModel):
    id: str
    label: str
    foodId: Optional[str] = None
    grams: Optional[float] = None
    per100g: Optional[MacroTotals] = None
    source: Optional[str] = None
    family: str = ""
    citationUrl: Optional[str] = None
    measures: list[HouseholdMeasure] = Field(default_factory=list)


class CommittedFood(BaseModel):
    foodId: str
    displayName: str
    per100g: MacroTotals
    source: str
    citationUrl: Optional[str] = None
    family: str = ""
    measures: list[HouseholdMeasure] = Field(default_factory=list)


class ResolveQueue(BaseModel):
    resolved: list[ResolvedItem] = Field(default_factory=list)
    pending: Optional[ItemDraft] = None
    remaining: list[ItemDraft] = Field(default_factory=list)
    committed: Optional[CommittedFood] = None
    clarifyOptions: list[ClarifyOption] = Field(default_factory=list)
    correctionEntryId: Optional[str] = None
    correctionItemIndex: Optional[int] = None
    correctionOp: Optional[str] = None


class SuggestionOptionItem(BaseModel):
    foodId: str
    displayName: str
    grams: Optional[float] = None
    source: Optional[str] = None
    provisionalPer100g: Optional[MacroTotals] = None
    per100g: Optional[MacroTotals] = None
    citationUrl: Optional[str] = None
    portionLabel: Optional[str] = None
    family: str = ""
    measures: list[HouseholdMeasure] = Field(default_factory=list)


class SuggestionOption(BaseModel):
    id: str
    title: str
    reason: str = ""
    items: list[SuggestionOptionItem] = Field(default_factory=list)
    totals: Optional[MacroTotals] = None
    fit: Literal["within", "over", "unknown"] = "unknown"
    overBy: Optional[dict[str, float]] = None


class PendingActionPayload(BaseModel):
    candidates: list[WorkingMemoryCandidate] = Field(default_factory=list)
    memoryText: Optional[str] = None
    suggestionOptions: list[SuggestionOption] = Field(default_factory=list)
    resolvedItems: list[ResolvedItem] = Field(default_factory=list)
    clarifyOptions: list[ClarifyOption] = Field(default_factory=list)
    entryId: Optional[str] = None
    dayKey: Optional[str] = None
    itemIndex: Optional[int] = None
    correctionOp: Optional[str] = None
    freeTextGrams: bool = False
    manualLog: bool = False
    reason: Optional[str] = None


class PendingAction(BaseModel):
    type: PendingActionType
    prompt: str = ""
    payload: PendingActionPayload = Field(default_factory=PendingActionPayload)

    @field_validator("payload", mode="before")
    @classmethod
    def _payload_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


class WorkingMemory(BaseModel):
    pendingIntent: Optional[str] = None
    clarifyingQuestion: Optional[str] = None
    candidates: list[WorkingMemoryCandidate] = Field(default_factory=list)
    pendingAction: Optional[PendingAction] = None
    resolveQueue: Optional[ResolveQueue] = None
    lastSuggestionOptions: list[SuggestionOption] = Field(default_factory=list)
    draftLog: list[ResolvedItem] = Field(default_factory=list)

    @field_validator("candidates", mode="before")
    @classmethod
    def _candidates_none_as_empty(cls, value: Any) -> Any:
        return [] if value is None else value

    @model_validator(mode="before")
    @classmethod
    def _drop_invalid_pending_action(cls, data: Any) -> Any:
        """Client may echo MealIntent into pendingAction.type; drop instead of 400."""
        if not isinstance(data, dict):
            return data
        pending = data.get("pendingAction")
        if not isinstance(pending, dict):
            return data
        try:
            PendingAction.model_validate(pending)
        except ValidationError:
            data = {**data, "pendingAction": None}
        return data


class ConversationContext(BaseModel):
    threadId: str = "default"
    summary: str = ""
    recentTurns: list[ConversationTurn] = Field(default_factory=list)
    workingMemory: Optional[WorkingMemory] = None


class InterpretContext(BaseModel):
    assistanceLevel: str = "fullAssist"
    responseStyle: str = Field(
        default="balanced",
        description="User dial: precise | balanced | creative (maps to LLM sampling).",
    )
    lastIntent: Optional[str] = None


class RecentCorrection(BaseModel):
    text: str
    at: str


class MemorySnapshot(BaseModel):
    preferences: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    diets: list[str] = Field(default_factory=list)
    regularTemplateIds: list[str] = Field(default_factory=list)
    recentCorrections: list[RecentCorrection] = Field(default_factory=list)


class InterpretMealRequest(BaseModel):
    utterance: str = ""
    timezone: str = "UTC"
    dayKey: str
    preferenceContext: PreferenceContext = Field(default_factory=PreferenceContext)
    diaryContext: DiaryContext
    longTermMemory: list[LongTermMemoryNote] = Field(default_factory=list)
    conversation: ConversationContext = Field(default_factory=ConversationContext)
    context: InterpretContext = Field(default_factory=InterpretContext)
    memorySnapshot: Optional[MemorySnapshot] = None


class FoodCandidate(BaseModel):
    foodId: str
    displayName: str
    grams: Optional[float] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    provisionalPer100g: Optional[MacroTotals] = None
    citationUrl: Optional[str] = None


class MemoryProposal(BaseModel):
    action: Literal["add", "update", "delete"]
    id: Optional[str] = None
    text: Optional[str] = None


class InterpretMealResponse(BaseModel):
    intent: MealIntent
    candidates: list[FoodCandidate] = Field(default_factory=list)
    clarifyingQuestion: Optional[str] = None
    correction: Optional[str] = None
    suggestedTemplateId: Optional[str] = None
    assistantMessage: str = ""
    warnings: list[str] = Field(default_factory=list)
    memoryProposals: list[MemoryProposal] = Field(default_factory=list)
    pendingAction: Optional[PendingAction] = None
    # Slot budget the suggestion was built for (stated, else typical meal, else weighted slot default).
    suggestionBudget: Optional[dict[str, float]] = None
    suggestionOptions: list[SuggestionOption] = Field(default_factory=list)
    workingMemory: Optional[WorkingMemory] = None
    conversation: Optional[ConversationContext] = None


class FoodHit(BaseModel):
    foodId: str
    displayName: str
    source: str
    per100g: MacroTotals
    family: str = ""
    measures: list[HouseholdMeasure] = Field(default_factory=list)


def _unwrap_firebase_number(value: dict[str, Any]) -> Any | None:
    """FirebaseDataEncoder may send Int64/Double as protobuf-shaped dicts."""
    type_name = str(value.get("@type") or "")
    if "Int64Value" not in type_name and "UInt64Value" not in type_name and "DoubleValue" not in type_name:
        return None
    raw = value.get("value")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def _normalize_payload(value: Any) -> Any:
    """Drop nulls and unwrap Firebase typed numbers for Pydantic."""
    if isinstance(value, dict):
        unwrapped = _unwrap_firebase_number(value)
        if unwrapped is not None:
            return unwrapped
        return {
            k: _normalize_payload(v)
            for k, v in value.items()
            if v is not None
        }
    if isinstance(value, list):
        return [_normalize_payload(v) for v in value]
    return value


def request_from_dict(data: dict[str, Any]) -> InterpretMealRequest:
    """Parse callable payload; synthesize diary remaining if missing for tests."""
    data = _normalize_payload(data)
    if not isinstance(data, dict):
        data = {}
    if "diaryContext" not in data:
        data = {
            **data,
            "diaryContext": {
                "today": [],
                "previousDays": [],
                "remaining": {
                    "calories": 2000,
                    "proteinG": 140,
                    "carbsG": 200,
                    "fatG": 65,
                },
                "remainingSource": "clientComputed",
            },
        }
    return InterpretMealRequest.model_validate(data)
