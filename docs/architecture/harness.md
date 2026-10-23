# Harness

The in-app model and an external MCP agent share one tool list. The model sees each tool result on the tool channel and may call the next tool, up to twelve tool rounds, then writes the reply. Offline tests set `CAPY_MOCK_AGENT=1`.

The system prompt is `functions/agent/harness/prompts/`. The harness builds it and passes the prompt and the registry tool declarations into the Gemini call. Tool descriptions live on the registry in `functions/agent/tools/`. USDA key: Secret Manager `USDA_FDC_API_KEY`.

## Layout

```text
functions/agent/
  graph.py            # prepare → llm ⇄ environment → format → respond
  turn.py             # those nodes
  tools/              # shared stateless tools and the Gemini registry
  llm/                # Gemini call. The harness passes the prompt in.
  thread_store.py     # conversation thread
  user_store.py       # profile, diary, library
  harness/
    prompts/          # system text, user text, assistance and reply-style dials
    execute.py        # bind uid, library, and diary, then call the tool
    policy.py         # confirm gate for the first in-app write
    diets.py          # mark diet and allergy conflicts on lookup hits
    suggestions.py    # cards from hits already fetched
    outcomes.py       # client outcome from the tool trace
    tool_args.py      # validate arguments against the registry
    save_memory.py    # remember / forget proposals (not a tool)
    portions.py       # grams from household units
    format.py         # assistant text from model prose or phrase facts
    messaging.py      # strip tool output from the chat reply
    mock_turn.py      # scripted model turns for tests
    checkpointer.py   # graph checkpoints
    memory/           # context pack, meal budget, and meal slots
```

`tools/search/` holds the catalog, USDA, library, and barcode clients, plus the Firestore food corpus and recipe stores. `memory/` builds the JSON pack (`assemble.py`: episodic, semantic, long-term). Notes and the diary are stored by `thread_store.py` and `user_store.py`.

Firebase callables in `main.py` are the iOS edge. Tools and those callables both call `user_api` / `user_store`. Tools do not call the callable handlers.

## Graph

```text
START → prepare → llm
llm --tool calls, under the cap--> environment → llm
llm --text, or cap hit--> format → respond → END
llm --infra failure twice--> respond
```

| Node | Where | What it does |
|------|--------|----------------|
| prepare | `turn.py` | Validate the request, build the memory pack, clear the previous turn's calls and outcome. |
| llm | `llm/model.py` | One Gemini call with the shared tools and Google Search grounding. Tool results from this turn go back as function responses. Bad arguments retry inside this step (max 2). |
| environment | `execute.py` | Run the calls. `diets.py` marks diet and allergy conflicts on hits. `policy.py` stages the first in-app write. `outcomes.py` builds the client outcome. |
| format | `format.py` | Use the model's prose when it sent some. Otherwise build a short line from tool facts. |
| respond | `turn.py` | `normalize_outcome()`. Infra failure is `warnings: ["agent_unavailable"]` and an empty message. |

`thread_id` is `{firebase_uid}:{conversation.threadId}` (default `default`). Tests use `MemorySaver`. Production checkpoints live in Firestore `agentGraphCheckpoints` (clients denied). Diary and remaining macros arrive fresh on each request.

The model may run twelve tool rounds. After each round it reads the function responses. A thirteenth tool call is dropped and the turn replies.

## Shared tools

Declared in `functions/agent/tools/`. The model passes the action arguments. `uid` is bound from auth. Library rows and diary rows are bound by the wrapper.

| Tool | Returns |
|------|---------|
| `search_catalog` | Seed catalog hits. Does not log. |
| `search_usda` | USDA FoodData Central hits, in FDC order. Does not log. |
| `search_library` | Strict match on the user's saved library. Does not log. |
| `lookup_barcode` | Open Food Facts for one GTIN. Miss is `found: false`. Does not log. |
| `portion_to_grams` | `{grams, label}` or `{unmapped: true}`. Does not guess. |
| `get_diary` | `{dayKey, entries, remaining}` for one day. |
| `write_food_entry` | Writes one entry: a food, a recipe, or a meal. Returns `{entryId, dayKey}`. `entry_id` replaces that one entry. |
| `delete_food_entry` | Deletes one entry. Unknown id is an error. The iPhone callable is `delete_meal`. |

The in-app wrapper marks a diet or allergy conflict on the hit (`conflict`: `diet` or `allergy`) and still returns it. The model decides whether to use it. The first in-app `write_food_entry` or `delete_food_entry` returns `{staged: true}` and sets `pendingAction`. The same call writes only when that pending action is already on the request and the food id, grams, and per100g still match. MCP writes on the call.

A log is search, then `portion_to_grams`, then one `write_food_entry`. One call is one food, one recipe, or one meal. Another food is another call. Several hits stay in the result. The model asks which one. A suggestion is a diary read plus lookups. The harness builds `suggestionOptions` from hits and gram amounts already fetched in that turn, and only when nothing was staged or written. An edit is `get_diary`, then `write_food_entry` with `entry_id`, or `delete_food_entry`.

## Not tools

- **Memory.** `save_memory.py` adds a `memoryProposals` entry when the utterance starts with "remember" or "forget". `format_reply` attaches it. The client applies it. There is no confirm step for memory.
- **MCP.** `functions/cloudrun/` is the Cloud Run app. `cloudrun/mcp/host.py` exposes the four lookups, `portion_to_grams`, `get_diary`, `write_food_entry`, `delete_food_entry`, `patch_profile`, and the library tools. See [mcp-tools.md](mcp-tools.md). The external agent calls those tools. `write_food_entry` and `delete_food_entry` on MCP write immediately. Direct lookups return the source hits with no `conflict` field. `interpret_meal` is the iPhone callable and is not an MCP tool.
- **Callables.** `log_meal`, `delete_meal`, profile, library, and barcode callables are the iPhone edge. They call `user_api`, the same bottom the tools use. See [api-contracts.md](api-contracts.md).
- **Ranker.** `tools/search/food_search.py` scores a pool for offline evals. The agent does not call it.

## Outcomes

At most one blocking action: `clarify_food`, `clarify_portion`, `confirm_log`, `confirm_correction`, `confirm_delete`.

A staged `write_food_entry` without `entry_id` is `confirm_log`. A staged `write_food_entry` with `entry_id` is `confirm_correction`. A staged `delete_food_entry` is `confirm_delete`. Suggestion cards are omitted when a write was staged.

Payloads: [api-contracts.md](api-contracts.md).
