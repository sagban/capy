"""One tool list for the in-app model and MCP. Schemas are the model-visible arguments."""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from agent.tools.diary_io import delete_meal, get_diary, write_food_entry
from agent.tools.lookups import lookup_barcode, search_catalog, search_library, search_usda
from agent.tools.portion import portion_to_grams
from agent.tools.schema import declaration

ToolFn = Callable[..., dict[str, Any]]


class SearchCatalogArgs(BaseModel):
    query: str = Field(min_length=1, description="Food name, such as rice, egg, or paneer.")
    limit: int = Field(default=10, ge=1, le=20, description="Maximum hits to return.")


class SearchUsdaArgs(BaseModel):
    query: str = Field(min_length=1, description="Food name to fetch from USDA FoodData Central.")
    limit: int = Field(default=8, ge=1, le=40, description="Maximum hits to return.")


class SearchLibraryArgs(BaseModel):
    query: str = Field(min_length=1, description="Saved food, recipe, or meal title.")
    limit: int = Field(default=3, ge=1, le=10, description="Maximum hits to return.")


class LookupBarcodeArgs(BaseModel):
    gtin: str = Field(min_length=1, description="Digits from the package barcode (UPC or EAN).")


class MeasureArg(BaseModel):
    id: str
    label: str
    grams: float


class PortionArgs(BaseModel):
    quantity: float = Field(gt=0, description="How many of the unit the user said.")
    unit: str = Field(min_length=1, description="Unit the user said, such as cup, large, or g.")
    measures: list[MeasureArg] = Field(
        default_factory=list,
        description="Household measures from the hit you chose. Pass them through unchanged.",
    )


class MacroArg(BaseModel):
    calories: float = Field(description="Kilocalories in 100 grams of this food. Not the portion.")
    proteinG: float = Field(description="Protein grams in 100 grams of this food.")
    carbsG: float = Field(description="Carbohydrate grams in 100 grams of this food.")
    fatG: float = Field(description="Fat grams in 100 grams of this food.")


class GetDiaryArgs(BaseModel):
    day_key: str = Field(min_length=1, description="Diary day YYYY-MM-DD.")


class WriteFoodEntryArgs(BaseModel):
    day_key: str = Field(min_length=1, description="Diary day YYYY-MM-DD.")
    meal_slot: str = Field(min_length=1, description="Slot name from the user's meal plan.")
    kind: Literal["food", "recipe", "meal"] = Field(description="What this one entry is: food, recipe, or meal.")
    name: str = Field(min_length=1, description="Name of this one entry. Use the lookup hit's displayName.")
    grams: float = Field(gt=0, description="Portion weight in grams, from portion_to_grams.")
    per100g: MacroArg = Field(
        description="Calories, protein, carbs, and fat for 100 grams of this entry. Copy the lookup hit's per100g unchanged. Do not scale it to the portion. The diary multiplies by grams/100.",
    )
    foodId: str | None = Field(default=None, description="Id from the lookup hit. Omit when no lookup had this entry.")
    source: str | None = Field(default=None, description="catalog, usda, library, or web.")
    ingredientFamily: str | None = Field(default=None, description="Family from the lookup hit, such as egg.")
    citationUrl: str | None = Field(default=None, description="Page the per100g numbers came from, when the entry was not in a lookup.")
    entry_id: str | None = Field(default=None, description="Existing entry to replace. Omit to create one.")
    client_mutation_id: str | None = Field(default=None, description="Idempotency key for this write.")


class DeleteMealArgs(BaseModel):
    day_key: str = Field(min_length=1, description="Diary day YYYY-MM-DD.")
    entry_id: str = Field(min_length=1, description="Entry to delete.")
    client_mutation_id: str | None = Field(default=None, description="Idempotency key for this delete.")


class ToolSpec:
    def __init__(
        self,
        name: str,
        description: str,
        args_model: type[BaseModel],
        fn: ToolFn,
        *,
        bind: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.description = description
        self.args_model = args_model
        self.fn = fn
        self.bind = bind


SEARCH_CATALOG = """Look up a generic food in the bundled seed catalog.

When to use: The user named a staple or a common food and you need per-100g numbers and measures.
When not to use: A barcode, a saved library title, or a meal you are ready to write. This does not log.
Hits keep catalog order. Pass the chosen hit's measures to portion_to_grams. Do not invent grams.
"""

SEARCH_USDA = """Fetch foods from USDA FoodData Central.

When to use: The catalog missed, or the user named a branded package.
When not to use: A staple you expect in the catalog, a barcode, or a write. This does not log.
Hits stay in FoodData Central order.
"""

SEARCH_LIBRARY = """Match a name against the signed-in user's saved library.

When to use: They used a personal title ("Gym Bowl") and you need that saved row.
When not to use: A generic staple, a brand that is not saved, or a barcode. This does not log.
Matching stays strict: a single generic word does not match a longer saved title.
"""

LOOKUP_BARCODE = """Look up one package barcode on Open Food Facts.

When to use: The user gave a UPC or EAN.
When not to use: You have a food name and no barcode. A miss is found false. Do not fill in macros.
"""

PORTION = """Turn a quantity and unit into grams using the hit's measures.

When to use: You chose a hit and the user named how much.
When not to use: You do not have a hit yet. Call a lookup first.
An unknown unit returns unmapped true. Do not guess a gram weight.
"""

GET_DIARY = """Read one day's diary entries and remaining macros.

When to use: You need entry ids to edit or delete, or today's foods before a suggestion.
When not to use: The context pack already has this day and you do not need a fresh read.
"""

WRITE_FOOD_ENTRY = """Write one diary entry: a food, a recipe, or a meal.

When to use: You already have one hit and grams from portion_to_grams, and the user agreed. One call writes one entry. Set kind to food, recipe, or meal. Copy that hit's per100g unchanged: calories, proteinG, carbsG, and fatG for 100 grams, not for the portion. Another food is another call. Pass entry_id to replace one existing entry.
When not to use: You have not looked it up, or the user has not agreed. Do not pass a list of foods. Saving a reusable library row is upsert_library_item. In the app the first call stages a confirm and does not write. Call it again with the same fields after they confirm.
"""

DELETE_MEAL = """Delete one diary entry.

When to use: The user wants that one entry gone. Pass day_key and entry_id from get_diary or the pack.
When not to use: The entry should change. Call write_food_entry with entry_id and the new fields.
In the app the first call stages a confirm and does not delete. Call it again after they confirm.
"""


def _write(
    uid: str,
    day_key: str,
    meal_slot: str,
    kind: str,
    name: str,
    grams: float,
    per100g: Any,
    foodId: str | None = None,
    source: str | None = None,
    ingredientFamily: str | None = None,
    citationUrl: str | None = None,
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
) -> dict[str, Any]:
    macros = per100g if isinstance(per100g, dict) else per100g.model_dump(mode="json")
    return write_food_entry(
        uid,
        day_key,
        meal_slot,
        kind,
        name,
        grams,
        macros,
        foodId=foodId,
        source=source,
        ingredientFamily=ingredientFamily,
        citationUrl=citationUrl,
        entry_id=entry_id,
        client_mutation_id=client_mutation_id,
    )


TOOLS: dict[str, ToolSpec] = {
    "search_catalog": ToolSpec("search_catalog", SEARCH_CATALOG, SearchCatalogArgs, search_catalog),
    "search_usda": ToolSpec("search_usda", SEARCH_USDA, SearchUsdaArgs, search_usda),
    "search_library": ToolSpec("search_library", SEARCH_LIBRARY, SearchLibraryArgs, search_library, bind=("items",)),
    "lookup_barcode": ToolSpec("lookup_barcode", LOOKUP_BARCODE, LookupBarcodeArgs, lookup_barcode),
    "portion_to_grams": ToolSpec("portion_to_grams", PORTION, PortionArgs, portion_to_grams),
    "get_diary": ToolSpec("get_diary", GET_DIARY, GetDiaryArgs, get_diary, bind=("entries", "remaining")),
    "write_food_entry": ToolSpec("write_food_entry", WRITE_FOOD_ENTRY, WriteFoodEntryArgs, _write, bind=("uid",)),
    "delete_food_entry": ToolSpec(
        "delete_food_entry",
        DELETE_MEAL,
        DeleteMealArgs,
        delete_meal,
        bind=("uid",),
    ),
}

LOOKUP_NAMES = frozenset({"search_catalog", "search_usda", "search_library", "lookup_barcode"})

TOOL_DECLARATIONS = [declaration(spec.name, spec.description, spec.args_model) for spec in TOOLS.values()]
