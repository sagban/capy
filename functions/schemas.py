"""Pydantic DTOs mirroring docs/architecture/api-contracts.md."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MealIntent(str, Enum):
    log_meal = "log_meal"
    suggest_meal = "suggest_meal"
    correct_meal = "correct_meal"
    clarify = "clarify"
    update_preference = "update_preference"
    update_memory = "update_memory"
    unknown = "unknown"


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


class DiaryDaySummary(BaseModel):
    dayKey: str
    mealCount: int
    itemNames: list[str] = Field(default_factory=list)


class DiaryContext(BaseModel):
    today: list[DiaryEntry] = Field(default_factory=list)
    previousDays: list[DiaryDaySummary] = Field(default_factory=list)
    remaining: MacroTotals
    remainingSource: str = "clientComputed"


class LongTermMemoryNote(BaseModel):
    id: str
    text: str


class ConversationTurn(BaseModel):
    role: str
    text: str


class WorkingMemoryCandidate(BaseModel):
    foodId: str
    displayName: str
    grams: Optional[float] = None


class WorkingMemory(BaseModel):
    pendingIntent: Optional[str] = None
    clarifyingQuestion: Optional[str] = None
    candidates: list[WorkingMemoryCandidate] = Field(default_factory=list)


class ConversationContext(BaseModel):
    summary: str = ""
    recentTurns: list[ConversationTurn] = Field(default_factory=list)
    workingMemory: Optional[WorkingMemory] = None


class InterpretContext(BaseModel):
    assistanceLevel: str = "fullAssist"
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
    utterance: str
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
    assistantMessage: str
    warnings: list[str] = Field(default_factory=list)
    memoryProposals: list[MemoryProposal] = Field(default_factory=list)


class FoodHit(BaseModel):
    foodId: str
    displayName: str
    source: str
    per100g: MacroTotals
    family: str = ""


def request_from_dict(data: dict[str, Any]) -> InterpretMealRequest:
    """Parse callable payload; synthesize diary remaining if missing for tests."""
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
