# Amazon App Dev 2026 submission checklist

Hackathon: [Build, Ship, Shape](https://amazonappdev2026.devpost.com) (`amazonappdev2026`).

Account: Sagar Bansal (`sagban`), already registered.

Devpost project: [Capy](https://devpost.com/software/cappy) (`cappy`, id 1500251). Draft submission `1254674` on `amazonappdev2026`. Not submitted.

**Deadline: Friday, October 23, 2026 at 12:00 PM PT (2:00 PM CT).** After that, leave the repo, video, and project page untouched until winners are announced on December 3.

Primary track: **Alexa+**. AWS Builder is deferred: answer **No** on the form until a named AWS service is actually called.

Submitting early does not freeze the page. Edit the writeup, video, and repo until the deadline. Confirm status says **Submitted**.

## 1. Make the demo satisfy Alexa+

Alexa+, Bee, and Ring each require the repo to call that track’s technology in code: an import, an entry point, or a loaded agent, flow, or MCP config. A README mention does not count.

Capy is on the MCP server path, not the simulated-experience path. The server is Streamable HTTP, spec 2025-11-25 or newer, in `functions/cloudrun/mcp/host.py`, mounted by `functions/cloudrun/app.py`. Cloud Run `capy-mcp` is the host: `POST https://capy-mcp-322403791923.us-central1.run.app/mcp/`. A request without a bearer returns `401`. The `/authenticate` page signs in and mints the token. It is not an Alexa+ simulation, so it does not satisfy the track by itself.

The simulated-experience alternative needs no particular SDK, but the simulation’s source has to be in the repo and the demo has to show that simulation working. We are not using that alternative.

- [x] Streamable HTTP MCP exposes the meal tools (lookups, `portion_to_grams`, `get_diary`, `write_food_entry`, `delete_food_entry`, library, profile)
- [ ] The demo shows that MCP server in action: say the meal, Capy confirms what was logged and what’s left, then a second turn (“add a coffee” or “I only ate half”) stays on the same day, and the iPhone Food Log shows that entry
- [x] Judges can run it from the README: install, the exact command, a bearer from `/authenticate`, and one egg logged with `search_catalog`, `portion_to_grams`, and `write_food_entry`
- [ ] No API keys in the repo. Secrets stay in env files that are gitignored

Account-linking pages for a shipped Alexa skill are not in this repo. This submission does not include them.

Other tracks, not ours: Fire TV accepts any framework, and the video has to show the project on a Fire TV device or the Fire TV/Vega simulator. Bee has to use live Bee data to do something for a user, in both the video and the code. Ring has to run on a Ring simulator or a Ring device.

## 2. Repo the judges can open

- [ ] GitHub URL that contains source, assets, and run instructions
- [ ] Either the repo is **public** and the MIT `LICENSE` is visible in the GitHub About section, or it stays **private** and these people are invited under Settings → Collaborators. A public repo does not need these invites. Open Source does, because that mini-challenge requires a public URL.
  - `testing@devpost.com`
  - `chris-trag`, `knmeiss`, `giolaq`, `anishamalde`, `mosesroth`, `emersonsklar`
- [ ] If the repo is private: add them when you submit, not earlier. Each person has to accept. GitHub invitations expire after 7 days. If one lapses, re-send it from the same Collaborators page. Judging runs past that window, so check again before a judge would open the repo.
- [x] README states the repo’s first commit is October 11, 2026, and lists what the window built

## 3. Video

- [ ] Public YouTube or Vimeo, English, under 3 minutes. Judges can stop at 3:00
- [ ] Order: the kitchen problem, say the meal, Capy confirms it and what’s left, a second turn that edits the same day, the iPhone Food Log showing that entry. The MCP server has to be visibly in that flow. One shot names Alexa+ and MCP. The rest is the product.
- [ ] No copyrighted music or footage you do not have rights to
- [ ] Uploaded before Friday morning so processing finishes

## 4. Devpost project page

- [ ] Name a person would repeat. 60 characters max
- [x] Tagline: “The meal you say becomes the line already on your phone.” Architecture stays in How we built it.
- [ ] Thumbnail is a product frame (the log, or the spoken confirmation), not a diagram
- [ ] Gallery: Food Log, the conversation, a before/after of one meal, then one architecture image
- [ ] Writeup: Inspiration, What it does, How we built it, Challenges, Accomplishments, What we learned, What’s next
- [ ] “How we built it” names Streamable HTTP or the simulation and the tool names. The trust boundary is one paragraph there, not the tagline.
- [ ] Built with includes `mcp`, `amazon-alexa`, `python`, `firebase`, `swift`
- [ ] Project link: the GitHub repo

Paste the sections below into the project page. The tagline is the promise. The required tech shows up inside How we built it, the way a badge scan, a PPE check, and an X-ray showed up in PneumoScan: each step is the product, and the API is how that step is true.

Suggested tagline: The meal you say becomes the line already on your phone.

### Inspiration

People do not fail at nutrition in a dashboard. They fail at the stove. Hands are wet, the pan is on, and the meal is one sentence: “two eggs and a coffee.” The apps on the market answer that sentence with a search box, a barcode hunt, or a chatbot that invents a calorie number and calls it logged.

A guessed egg is worse than a missed egg. It sits in the day as if it were measured. The next sentence, “I only ate half,” has nothing real to edit. The phone and the kitchen end up with two different mornings.

Capy starts from the sentence and refuses the guess. The food is looked up. The portion you said becomes grams. The line that lands in the diary carries the numbers from that food, for 100 grams, and the day multiplies. Alexa+ is where the sentence is spoken. The iPhone Food Log is where the line has to appear, unchanged.

### What it does

1. You say the meal. Capy does not reply with a plan for your life. It finds the food, converts “two large eggs” with that food’s own measures, and writes one line. A coffee is a second line. A recipe you saved is one line of its own. The reply names what was logged and what is left.
2. The next sentence is the same morning. “Add a coffee” writes the coffee. “I only ate half” reads today’s diary and replaces that one entry. It does not open a new chat and hope the model remembers.
3. The Food Log on the phone shows those lines. The kitchen and the pocket are one record. On the phone, the first write waits until you confirm that same food, those grams, and those numbers. Alexa+, having already heard you, writes on the call.

There is no streak, no score, and no “you should.” If a food conflicts with a diet or an allergy, the hit stays visible and marked. The model decides in the open. It does not quietly drop the plate and pretend the search was empty.

### How we built it

The sentence is three tool calls, and the model is not allowed to skip them with a made-up plate.

1. Find the food. `search_catalog`, `search_usda`, `search_library`, or `lookup_barcode`. A saved meal matches the title, not a loose word: “chicken” is not “Sunday Chicken Feast.”
2. Convert the portion. `portion_to_grams` uses the measures on that hit. An unknown unit comes back unmapped. Capy does not invent 100 grams for a whole plate.
3. Write one line. `write_food_entry` takes the name, the grams, and `per100g` copied from the hit: calories, protein, carbs, and fat for 100 grams, not scaled to the portion. The diary does the multiplication. A second food is a second call. An edit is `get_diary`, then the same write with that entry’s id, or `delete_food_entry` for the one line that should go.

Alexa+ reaches those tools through a self-hosted MCP server, Streamable HTTP, spec 2025-11-25. The server is `functions/cloudrun/mcp/host.py`, mounted at `POST /mcp/` by `functions/cloudrun/app.py`. `initialize` returns `protocolVersion` `2025-11-25`. The bearer is the person. No bearer, no diary: the route returns `401`. `GET /authenticate` signs in with the same email and password as the phone and hands back a one-hour token plus an MCP config.

The phone’s own agent is the only caller of `interpret_meal`. It passes the same tool list into the model and reads each result as a function response, not as text pasted into the chat. The first in-app write stages a confirm. The write goes through only when the food id, the grams, and the per-100g numbers still match what was shown. MCP writes immediately, because the person already said the meal out loud.

### Challenges

The spec Alexa+ asks for is not the tutorial you find first. Streamable HTTP sits still until the process runs its session manager for the life of the server, and the default host check rejects the host Cloud Run actually sends. The server that works is `POST /mcp/`, bearer auth, stateless, JSON response, trailing slash required. SSE would have been a README. It would not have been this track.

The second trap was treating a name and a weight as a meal. Early writes stored missing macros as zero and still said the food was logged. A zero-calorie egg is the same lie as a guessed egg. The write now refuses to land without `per100g`.

Account linking is a second login on top of the one the person already has. We can show the diary from a bearer minted at `/authenticate`. We cannot yet show a skill that stays linked past an hour. That limit is in the demo on purpose. A kitchen that dies at minute 61 is not shipped.

### Accomplishments

One record, two doors. The sentence in the kitchen and the tap on the phone land on the same lines, with numbers that came from a food someone can cite. The model can talk. It cannot mint the plate.

### What we learned

A meal agent that hides its work becomes another tracker. Hide a diet conflict and the model recommends the food anyway. Paste tool output into the chat and the model recites JSON. Give it a name and a weight with no per-100g numbers and it logs a confident zero. The useful system shows the hit, marks the conflict, and writes only what the lookup actually returned.

### What’s next

A token that lasts a cooking session, then the authorize page and token endpoint so Alexa account linking issues that same bearer. The diary path is the one we would keep. The hour-long paste is the part we would not ship.

### Form: what changed in the window

Capy keeps one diary for the kitchen and the phone. This repository’s first commit is October 11, 2026. In the window we built the Food Log and a self-hosted MCP server (Streamable HTTP, spec 2025-11-25) at `POST /mcp/`. A spoken meal is a lookup, a portion, and one `write_food_entry` whose `per100g` is copied from the food, not invented. A second sentence edits that same day. The video shows that line on the iPhone.

### Form: Open Source description

`https://github.com/sagban/capy` is MIT, copyright 2026 Sagar Bansal, GitHub `sagban`. The work is a diary a spoken meal can write without the model inventing the numbers. Alexa+ calls the MCP server. The phone shows the same lines. A food is found, the portion becomes grams, and one entry is written with cited per-100g calories, protein, carbs, and fat. That is the difference between a log and a chatbot that guessed breakfast.

## 5. Submission form

Create the project against hackathon `amazonappdev2026`, then fill these. Required unless marked optional.

- [ ] Submitter type: Individual
- [ ] Organization name: `N/A`
- [ ] Country: United States
- [ ] Canada province: `N/A`
- [ ] Primary track: **Alexa+** only
- [ ] Code repository URL
- [ ] New, or Existing but significantly updated since August 31, 2026
- [ ] If existing: what you built during the window, and that the video shows that part
- [ ] AWS Builder mini-challenge: **No** for this pass. Revisit only after Alexa+ is submitted.
- [ ] AWS services writeup: `N/A — not entering AWS Builder`
- [ ] Open Source mini-challenge: **Yes** on this same submission. MIT `LICENSE` is in the repo root (copyright 2026 Sagar Bansal). Commit and push it, and keep `https://github.com/sagban/capy` public so GitHub shows MIT in About. A private repo does not qualify, even with judge invites.
- [ ] If Yes: contribution URL, repo URL `https://github.com/sagban/capy`, GitHub username `sagban`, and a short description of what you did, how it works, and why it matters
- [ ] Feedback 1–5: paste the drafts in [Feedback answers](#feedback-answers). They are not on the Devpost form yet.
- [ ] AI tools used while building
- [ ] Learning from the project: None / Moderate / Significant
- [ ] AI value you can use in your career: Yes or No
- [ ] Age of majority: checked
- [ ] Eligible jurisdiction: checked (United States is eligible)
- [ ] Not an employee of Amazon, Devpost, or their affiliates: checked
- [ ] Optional testing link and the credentials or steps a judge needs
- [ ] Optional feature requests, each with a priority: Critical, Important, or Nice-to-have
- [ ] Optional friction log URL. Worth up to a 10% judging bonus. Each entry needs the task, the steps, expected vs actual, a severity, the workaround, and a concrete suggestion

## 6. Submit, then polish

- [ ] Hit Submit on [Capy](https://devpost.com/software/cappy) and confirm the status says **Submitted**
- [ ] Replace the rough video if a tighter cut is ready
- [ ] If the repo is private, confirm every collaborator invite is accepted. Re-send any that expired from Settings → Collaborators.

## Feedback answers

Drafts for the five required questions. Grounded in the repo: FastMCP tools, Streamable HTTP at `POST /mcp/`, and a one-hour bearer from `/authenticate`. Account-linking pages are not shipped.

Not entered: Fire TV, Ring, Bee, or AWS runtime services.

### 1. Which developer tools, APIs, and SDKs did you use and for what?

Three, all for the Alexa+ path into an existing food log.

The MCP Python SDK (`mcp` 1.x, FastMCP; 2.x removed FastMCP) exposes the meal actions as tools: the food lookups, `portion_to_grams`, `get_diary`, `write_food_entry`, `delete_food_entry`, `patch_profile`, and the library tools. The external agent calls those tools. The iPhone still calls `interpret_meal`, `get_thread`, and `patch_thread` as Firebase callables. MCP is the door Alexa+ uses, so a spoken meal writes the same diary.

The MCP Streamable HTTP transport in the 2025-11-25 spec is how that server is mounted. `POST /mcp/` speaks JSON-RPC. `initialize` returns `protocolVersion` `2025-11-25`. The tools run in-process on Cloud Run.

Alexa account linking (Auth Code Grant in the Alexa Developer Console) is how a skill would receive a bearer for those APIs. The authorize page and token endpoint are not in the repo. Until they exist, we mint a one-hour token with `exchange_access_token` and paste it into the skill test Access Token field.

### 2. For each tool, API, or SDK, what worked well?

MCP Python SDK. A tool is a function plus a schema, so the hosted server calls the same meal handlers the iPhone uses. A bearer-authenticated meal tool is callable from an MCP client without a second copy of the agent. `initialize` negotiates `protocolVersion` `2025-11-25`.

The 2025-11-25 spec. It is explicit that the integration is one Streamable HTTP endpoint. That stopped us from treating an SSE URL in the README as an Alexa+ submission.

Alexa account linking. The console fields map onto OAuth: authorization URI, access token URI, Auth Code Grant, HTTP bearer. Alexa opens the authorize URL with `client_id`, `response_type`, `state`, and `redirect_uri`. The token endpoint returns `access_token`, `token_type`, and `expires_in`. That token is the same bearer shape `exchange_access_token` already mints for the callables and the MCP host.

### 3. For each tool, API, or SDK, what needs work?

MCP Python SDK. The short path is still SSE (`sse_app` at `/sse` and `/messages/`). Streamable HTTP is a second app, `streamable_http_app`, and its session manager does nothing until the parent process runs `session_manager.run()` in the ASGI lifespan. Skip that and every request fails with "Task group is not initialized." The default transport security also rejects any `Host` that is not localhost, which is what Cloud Run sends. We turned that check off because bearer auth is the real gate. A getting-started page that mounts Streamable HTTP with bearer auth, names the lifespan call, and marks SSE as legacy would match the spec this track requires. `mcp` 2.0 also removed `FastMCP` with no in-repo bridge, so a fresh `pip install mcp` breaks an existing server.

Alexa+ and the spec, together. The hackathon points at the MCP spec, at Build with Agent Skills, and at a simulated web app if you are new to MCP. It does not say which of the three a food log should ship, or how an Alexa+ client discovers a self-hosted server and attaches the user’s bearer. We can build the server. We cannot point at a page that shows Alexa+ calling it.

Account linking. The authorize webview and token endpoint are a second login on top of Firebase Auth: client id, client secret, domain list, one-time code, redirect back to `alexa.amazon.com`. That is a product of its own before one meal is logged. The working path is a token pasted into the developer console. It expires in 3600 seconds, and a refresh token is left optional. A kitchen skill that dies every hour is not something we can ship. Linking also must not be pointed at MCP OAuth scopes. The skill receives the bearer, and the skill backend presents it to MCP. That split is right, and the console makes it easy to wire the wrong way.

### 4. How was onboarding, from zero to hello world?

MCP SDK, to a local tool. Short. Install `mcp`, declare the FastMCP tools, call `search_catalog` and `write_food_entry` with a bearer. We were hitting our own functions the same day.

MCP SDK, to a URL this track accepts. Longer than a local process. SSE is the example you find first. Streamable HTTP needed `streamable_http_path`, `stateless_http` so Cloud Run does not keep a session in memory, `json_response` so a client can read the body, the lifespan hook, and the localhost host check turned off. After that, `POST /mcp/` with `Accept: application/json, text/event-stream` returns `protocolVersion` `2025-11-25`. The URL also has to keep the trailing slash; `/mcp` is a redirect.

Alexa console, to a linked user logging a meal. Not finished. The console itself is understandable. What is missing is a minimal authorize page and token endpoint that returns a bearer for an account the user already has, and a refresh token so the link survives the hour. Our onboarding stops at “paste a one-hour token into the test field.”

### 5. Would you build with these devices and services again?

Yes for MCP as the way Alexa+ reaches an app we already have. One tool list serves the phone and the kitchen. The follow-up (“add a coffee”, “I only ate half”) works because the thread tools keep the day. We would build on that again.

Yes for Alexa+ if the supported path is that MCP server on Streamable HTTP, with one documented way to attach the user’s token.

We would not start again from a classic custom skill and an Auth Code Grant webview as the only door. It repeats Firebase sign-in, the sample ends at a one-hour pasted token, and it is a different integration from the MCP server the track asks for. A Streamable HTTP hello world and a token that lasts longer than a cooking session, and the answer is yes without that caveat.
