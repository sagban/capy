# Capy — hackathon write-up (draft)

Draft for approval. Not on the Devpost page yet.

Awareness gap, not willpower gap.

## Inspiration

People want to stay fit and healthy. What they lack is a clear picture of the daily actions that get them there. Food tracking is one of those actions. The tools that offer it make the action harder than the meal: a search box, a barcode, a diet plan that expires in a week. People chase the plan, miss the day, and decide they failed.

We are building Capy so the daily action is eating. You say what you want. Capy finds a meal that fits the budget you have left and that you will actually eat. The diary fills in behind that. Tracking is the side effect of living the day.

## The problem

Staying in budget is a daily question: what can I eat now, with what I have left. Current trackers answer with a form. You stop cooking, look up each food, guess a portion, and hope the number is real. The next sentence, “I only ate half,” has nothing solid to change.

Diets and meal plans promise a way through that. Most of them ask for a new identity on Monday and a blank log by Wednesday. The person did not run out of willpower. They never got a meal that fit today, that they liked, and that landed in the log without a second job.

## What Capy does

Capy is a food log you talk to.

You say the meal, or you ask what fits. Capy looks the food up, turns the portion you named into grams, and writes one line with that food’s own calories and macros. A second food is a second line. “I only ate half” reads today’s diary and replaces that one entry. The reply names what was logged and what is left: calories, protein, carbs, and fat.

When you ask what to eat, Capy uses what is left in the day and what you actually eat. A vegetarian day does not come back as chicken. A meal you love can stay in the library and be logged again by name. The budget is the ceiling. The plate is something you would eat.

On the phone, the first write waits until you confirm that food, those grams, and those numbers. The Food Log is the same diary.

## Why Alexa+ matters

The moment that matters is when your hands are busy and the meal is one sentence. Alexa+ is that sentence. It reaches Capy through a self-hosted MCP server, Streamable HTTP, spec 2025-11-25, at `POST /mcp/`. The same tools that log a meal on the phone — look up the food, convert the portion, write one entry, read the day, edit one line — are the tools Alexa+ calls. No bearer, no diary.

Alexa+ is how tracking leaves the form. You ask for a meal, you stay in budget, you eat something you like. The log is already written.

## How we built it

Alexa+ and the phone share one diary. Alexa+ speaks the meal. The phone confirms it. Both doors use the same tools and the same record.

![Capy on AWS. Alexa+ and the iPhone share one diary.](../assets/hackathon/capy-architecture.png)

A meal is three tool calls. The model is not allowed to skip them with a made-up plate.

1. Find the food. `search_catalog`, `search_usda`, `search_library`, or `lookup_barcode`. A saved meal matches the title, not a loose word: “chicken” is not “Sunday Chicken Feast.”
2. Convert the portion. `portion_to_grams` uses the measures on that hit. An unknown unit comes back unmapped. Capy does not invent 100 grams for a whole plate.
3. Write one line. `write_food_entry` takes the name, the grams, and `per100g` copied from the hit: calories, protein, carbs, and fat for 100 grams, not scaled to the portion. The diary does the multiplication. A second food is a second call. An edit is `get_diary`, then the same write with that entry’s id, or `delete_food_entry` for the one line that should go.

Alexa+ reaches those tools through a self-hosted MCP server, Streamable HTTP, spec 2025-11-25. The server is `functions/cloudrun/mcp/host.py`, mounted at `POST /mcp/` by `functions/cloudrun/app.py`. `initialize` returns `protocolVersion` `2025-11-25`. The bearer is the person. No bearer, no diary: the route returns `401`. `GET /authenticate` signs in with the same email and password as the phone and hands back a one-hour token plus an MCP config.

The phone’s own agent is the only caller of `interpret_meal`. It passes the same tool list into the model and reads each result as a function response, not as text pasted into the chat. The first in-app write stages a confirm. The write goes through only when the food id, the grams, and the per-100g numbers still match what was shown. MCP writes immediately, because the person already said the meal out loud.

## Challenges we ran into

The spec Alexa+ asks for is not the tutorial you find first. Streamable HTTP sits still until the process runs its session manager for the life of the server, and the default host check rejects the host Cloud Run actually sends. The server that works is `POST /mcp/`, bearer auth, stateless, JSON response, trailing slash required. SSE would have been a README. It would not have been this track.

The second trap was treating a name and a weight as a meal. Early writes stored missing macros as zero and still said the food was logged. A zero-calorie egg is the same lie as a guessed egg. The write now refuses to land without `per100g`.

Account linking is a second login on top of the one the person already has. We can show the diary from a bearer minted at `/authenticate`. We cannot yet show a skill that stays linked past an hour. That limit is in the demo on purpose. A kitchen that dies at minute 61 is not shipped.

## Accomplishments that we're proud of

One record, two doors. The sentence in the kitchen and the tap on the phone land on the same lines, with numbers that came from a food someone can cite. The model can talk. It cannot mint the plate.

## What we learned

A meal agent that hides its work becomes another tracker. Hide a diet conflict and the model recommends the food anyway. Paste tool output into the chat and the model recites JSON. Give it a name and a weight with no per-100g numbers and it logs a confident zero. The useful system shows the hit, marks the conflict, and writes only what the lookup actually returned.

## What's next for Capy

Today is one meal and what is left. The next step is the week, sorted from the foods you already eat.

1. Ask Alexa+ what fits the next seven days. Capy builds that week from the diary, the library, and the diet you already keep. A vegetarian week stays vegetarian. A meal you log twice becomes a repeat, not a new plan to abandon.
2. Connect a grocery app. The week becomes a cart: what to buy, in the amounts those meals need. You shop once. The daily question, “what can I eat now,” already has an answer in the kitchen.
3. Keep the same diary. Each night’s sentence still looks the food up, turns the portion into grams, and writes one cited line. The week is only true if those lines are.
4. A token that lasts longer than a cooking session, so the grocery link and the diary stay signed in. The one-hour paste is the part we would not ship.

## Built with

`mcp`, `amazon-alexa`, `python`, `firebase`, `swift`
