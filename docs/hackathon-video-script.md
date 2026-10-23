# Capy — demo video script

Shoot this. The skeleton below is **1:34**. Let the replies sit, and the cut lands near **1:50**. Hard stop **2:40**. Judges can leave at 3:00, and they are not required to watch past it.

Public YouTube or Vimeo. English. No music you do not own. No Alexa chime, no Amazon logo. Say the meal in your own voice. The name **Alexa+** appears once, on the card and in one spoken line.

The running host is Cloud Run. Do not show the AWS architecture diagram, and do not say Bedrock, Lambda, or App Runner.

## What the judge must see, in this order

1. The kitchen problem.
2. You say the meal.
3. Capy names what was logged and what is left.
4. A second sentence edits that same day.
5. The iPhone Food Log shows those lines.
6. One shot that names Alexa+ and MCP, with the server visible in the flow.

## How Alexa appears

There is no Echo, no Alexa app, and no linked skill in this repo. Account linking stops at a one-hour token. Do not film a speaker and pretend it wrote the diary.

Alexa+ is the client. On screen, that client is an MCP chat that loaded the config from `GET /authenticate` (`mcpServers.capy.url` plus the bearer). Cursor or any other MCP host is fine. The chat has to show the tool calls, not a paragraph that recites them.

Record it in this order, one screen recording:

1. The chat, signed in. Blur the token if the config is visible. A corner label reads **Alexa+**.
2. You type the meal. The trace shows `search_catalog` or `search_usda`, then `portion_to_grams`, then `write_food_entry`. Hold each name long enough to read.
3. The reply names what was logged and what is left.
4. You type “I only ate half the rice.” The same day updates. The trace shows `get_diary`, then `write_food_entry` with that entry’s id.
5. Cut to the iPhone Food Log. Same foods, same numbers.

The card at 1:10 is where you say the name. The chat is where a judge sees the call.

## Record these four takes

| Take | What | Keep |
| --- | --- | --- |
| A | Your voice, the two sentences below. Quiet room. | Both lines, clean |
| B | MCP chat labeled Alexa+. Type the meal. Tool trace, then the reply with calories and what is left | The three tool names, then the reply held for 3 seconds |
| C | Same chat, same day. “I only ate half the rice.” One line replaced | Before and after on one day |
| D | iPhone Food Log, same foods, same numbers. Then the confirm card if it is one tap away | The log. Confirm is optional |

Cut the tool names in as a lower third over take B. They have to be readable. That is the MCP server in the flow. The title card is the one place the words Alexa+ and MCP are spoken.

Replace the bracketed numbers with whatever the app actually prints. Do not dub a number the screen does not show.

## The cut

### 0:00 — Open (0:08)

Card 1, full frame.

**On screen**

Capy

The meal you say becomes the line on your phone.

**Voice**

Hands are busy. The meal is one sentence. The tracker hands you a form and asks you to guess.

### 0:08 — Say the meal (0:22)

Take B. The MCP chat, corner label **Alexa+**. Your mouth is not in frame.

**You type, and say out loud**

Two large eggs and a cup of rice.

**Lower third, as the reply arrives**

Find the food.

Turn the portion into grams.

Write one line.

**Voice, once the reply is up**

Capy looks the foods up, turns what you said into grams, and writes one line each. The numbers come from the food.

**Hold the reply.** Read nothing the screen does not say. If the app prints a sentence like “logged … [N] cal left,” let that sentence sit. Then:

It names what landed, and what is left.

### 0:30 — Same morning (0:22)

Take C. Do not open a new chat. Stay on today.

**You**

I only ate half the rice.

**Voice**

Same day. It reads the diary and replaces that one line.

**Hold** the updated line. The rice grams drop. What is left goes up. If the app shows both foods, point at the rice with a cursor or a finger. Do not explain protein.

### 0:52 — The phone (0:18)

Take D. Food Log, today, eggs and rice, the halved rice.

**Voice**

The phone is the same diary.

If the confirm card is already on the reel, three seconds, no extra line:

Log 2 large eggs? — grams, calories, Confirm.

**Voice, only if that card is on screen**

On the phone, the first write waits until you confirm that food, those grams, and those numbers.

### 1:10 — The one tech shot (0:16)

Card 3. Full frame. This is the only time you explain the system.

**On screen**

Alexa+

Same tools. MCP. Streamable HTTP.

POST /mcp/

The model can talk. It cannot mint the plate.

**Voice**

Alexa+ calls those same tools over MCP. No bearer, no diary. The model can talk. It cannot mint the plate.

If you have a three-second screen recording of the three calls (`search_catalog` or `search_usda`, `portion_to_grams`, `write_food_entry`) or of a request with no bearer returning 401, lay it under this card at 30% opacity or as a one-second insert before the card. Do not narrate the status code.

### 1:26 — Close (0:08)

Card 4.

**On screen**

One diary. Two doors.

Tracking follows the meal.

**Voice**

You eat. The log is already written.

Fade out on the Food Log, not on a logo.

## Lines to record, nothing else

1. Hands are busy. The meal is one sentence. The tracker hands you a form and asks you to guess.
2. Two large eggs and a cup of rice.
3. Capy looks the foods up, turns what you said into grams, and writes one line each. The numbers come from the food.
4. It names what landed, and what is left.
5. I only ate half the rice.
6. Same day. It reads the diary and replaces that one line.
7. The phone is the same diary.
8. On the phone, the first write waits until you confirm that food, those grams, and those numbers.
9. Alexa+ calls those same tools over MCP. No bearer, no diary. The model can talk. It cannot mint the plate.
10. You eat. The log is already written.

About 145 words. At a calm pace that is under ninety seconds of voice. The rest is holds.

## Leave out

- The week, the grocery cart, and the one-hour token. Those live in the write-up.
- Streaks, scores, and “you should.”
- A tour of files, Cloud Run, or the sign-in page.
- Any number you did not just capture.

## Export

1920×1080, 30 fps. Captions on, burned in. Title: **Capy — say the meal**. Description, first line: The meal you say becomes the line already on your phone. Unlisted is not enough. The hackathon asks for a public video.
