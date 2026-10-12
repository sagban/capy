#!/usr/bin/env bash
# Seed Cappy GitHub backlog (epics + child issues). Idempotent enough for first run.
set -euo pipefail
export PATH="/opt/homebrew/bin:$PATH"
REPO="${REPO:-sagban/capy}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/scripts/.backlog_issue_map.tsv"
: > "$OUT"

create_issue() {
  local title="$1"
  local body="$2"
  local milestone="$3"
  shift 3
  local labels=("$@")
  local args=(issue create --repo "$REPO" --title "$title" --body "$body" --milestone "$milestone")
  local l
  for l in "${labels[@]}"; do
    args+=(--label "$l")
  done
  local url
  url="$(gh "${args[@]}")"
  local num
  num="$(basename "$url")"
  printf '%s\t%s\t%s\n' "$num" "$title" "$url" >> "$OUT"
  # stdout must be only the issue number (for capture); log to stderr
  printf 'created #%s %s\n' "$num" "$title" >&2
  printf '%s\n' "$num"
}

body_epic() {
  local track="$1" scope="$2" phase="$3"
  printf '%s\n' \
    "## Epic" \
    "" \
    "| Field | Value |" \
    "|-------|-------|" \
    "| **Track** | ${track} |" \
    "| **Phase** | ${phase} |" \
    "| **Scope** | ${scope} |" \
    "" \
    "### Locked decisions" \
    "- Firebase Auth: Sign in with Apple + Google Sign-In" \
    "- Python Firebase Functions + LangGraph + Gemini (backend proxy for keys)" \
    "- iPhone only; in-app check-ins (no push for V1)" \
    "- IA: TabView — Capy (default) / Food Log / Library; Settings top-right" \
    "- UI: native SwiftUI + Apple liquid-glass/materials; fixed App Color Palette" \
    "- Verifier: calories ≤ remaining; every macro within ±10%" \
    "- Memories/prefs/diets: explicit/user-editable only" \
    "- Deterministic maths never trusted from the LLM" \
    "" \
    "### Children" \
    "Child issues will be linked via comments after creation."
}

body_std() {
  local track="$1" prd="$2" summary="$3" acceptance="$4" deps="$5" oos="$6"
  # acceptance may contain literal \n sequences — expand them
  acceptance="${acceptance//\\n/$'\n'}"
  printf '%s\n' \
    "## Summary" \
    "${summary}" \
    "" \
    "| Field | Value |" \
    "|-------|-------|" \
    "| **Track** | ${track} |" \
    "| **PRD** | ${prd} |" \
    "" \
    "## Acceptance criteria" \
    "${acceptance}" \
    "" \
    "## Dependencies" \
    "${deps}" \
    "" \
    "## Out of scope" \
    "${oos}"
}

echo "Creating epics..."

E0=$(create_issue "[Epic] E0 Infra, docs, design (Phase 0)" \
  "$(body_epic "Infra/Docs/Design" "Cloud, architecture, screens, Cursor rules, UI design" "Phase 0")" \
  "Phase 0 — Infra and Docs" epic docs infra design phase-0 p0)

E1=$(create_issue "[Epic] E1 Auth & platform wiring" \
  "$(body_epic "Infra" "Apple + Google auth implementation (provisioning in Phase 0)" "Phase 0–2")" \
  "Phase 2 — UI Core" epic infra phase-2 p0)

E2=$(create_issue "[Epic] E2 Deterministic nutrition core" \
  "$(body_epic "Core math" "FR-2…FR-5 remaining maths, variety, verifier" "Phase 1 / 3")" \
  "Phase 1 — Harness Core" epic core-math phase-1 p0)

E3=$(create_issue "[Epic] E3 Food DB, seed, search/cache" \
  "$(body_epic "Data" "FR-6 USDA fallback, composites, seed catalog" "Phase 1")" \
  "Phase 1 — Harness Core" epic data phase-1 p0)

E4=$(create_issue "[Epic] E4 LangGraph AI harness" \
  "$(body_epic "Harness" "FR-1 structured parse, tools boundary, memories snapshot" "Phase 1")" \
  "Phase 1 — Harness Core" epic harness phase-1 p0)

E5=$(create_issue "[Epic] E5 Tab: Capy (AI screen)" \
  "$(body_epic "UI" "Default tab; agentic core experience" "Phase 2")" \
  "Phase 2 — UI Core" epic ui phase-2 p0)

E6=$(create_issue "[Epic] E6 Tab: Food Log" \
  "$(body_epic "UI" "Goals, daily log, day switcher, insights" "Phase 2")" \
  "Phase 2 — UI Core" epic ui phase-2 p0)

E7=$(create_issue "[Epic] E7 Tab: Library" \
  "$(body_epic "UI" "Custom meals/recipes/foods + AI-generated" "Phase 2")" \
  "Phase 2 — UI Core" epic ui phase-2 p0)

E7B=$(create_issue "[Epic] E7b Settings (toolbar)" \
  "$(body_epic "UI" "Goals, prefs, diets, Capy settings, user details" "Phase 2")" \
  "Phase 2 — UI Core" epic ui phase-2 p0)

E8=$(create_issue "[Epic] E8 Assistance dial & policy" \
  "$(body_epic "Both" "FR-7 Full Assist / Guided / Quiet" "Phase 1–3")" \
  "Phase 3 — Integration Loop" epic harness ui phase-3 p0)

E9=$(create_issue "[Epic] E9 Golden evals & ship gates" \
  "$(body_epic "Eval" "Launch bar p.9 golden set and dial evals" "Phase 4")" \
  "Phase 4 — Polish and Evals" epic eval phase-4 p0)

E10=$(create_issue "[Epic] E10 Post-October (P2)" \
  "$(body_epic "Deferred" "FR-9, FR-10, later roadmap" "Phase 5")" \
  "Phase 5 — Post-October (P2)" epic p2 phase-5)

echo "Epics: E0=$E0 E1=$E1 E2=$E2 E3=$E3 E4=$E4 E5=$E5 E6=$E6 E7=$E7 E7b=$E7B E8=$E8 E9=$E9 E10=$E10"

# ---------- Phase 0 children ----------
echo "Creating Phase 0 issues..."

create_issue "[Infra] Provision Firebase project + iOS app + Auth (Apple, Google)" \
  "$(body_std "infra" "—" \
    "Create Firebase project and iOS app registration; enable Sign in with Apple and Google Sign-In; document project IDs and environments." \
    "- [ ] Firebase project created and linked to iOS bundle id sagar.capy (or documented final id)\n- [ ] Apple + Google providers enabled with console checklists completed\n- [ ] Project IDs / env (dev) recorded in docs/runbooks/local-dev.md\n- [ ] No secrets committed" \
    "Parent epic #$E0" \
    "App UI auth screens (Phase 2); production App Check enforcement")" \
  "Phase 0 — Infra and Docs" infra docs phase-0 p0

create_issue "[Infra] Secret Manager + Vertex Gemini + USDA key runbook" \
  "$(body_std "infra" "—" \
    "Plan Python 2nd-gen Cloud Functions hosting for LangGraph; Secret Manager for Gemini + USDA; Vertex AI on same GCP project; cost/quota notes." \
    "- [ ] Region + IAM plan documented\n- [ ] Secret names listed (Gemini, USDA); never in git\n- [ ] Vertex/Gemini access checklist\n- [ ] USDA FoodData Central key acquisition steps\n- [ ] Dogfood cost/quota notes\n- [ ] App Check posture decided (document vs enforce later)" \
    "Blocked by Firebase project issue; parent #$E0" \
    "Implementing Functions code (Phase 1)")" \
  "Phase 0 — Infra and Docs" infra docs phase-0 p0

create_issue "[Infra] Emulator Suite layout + local secrets policy" \
  "$(body_std "infra" "—" \
    "Document Auth + Functions emulator layout, local .env pattern, and networking/callable auth contract notes." \
    "- [ ] Emulator services listed in runbook\n- [ ] Local env example without real keys\n- [ ] Callable auth (ID token) contract summarized\n- [ ] Optional CI skeleton decision recorded (GHA for Python later)" \
    "Parent #$E0" \
    "CI implementation beyond decision")" \
  "Phase 0 — Infra and Docs" infra docs phase-0 p0

create_issue "[Docs] System architecture overview + trust boundary" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/overview.md\`: SwiftUI ↔ SwiftData ↔ deterministic core ↔ Firebase Auth ↔ LangGraph ↔ Gemini/USDA." \
    "- [ ] Diagram present\n- [ ] Trust boundary: LLM never owns macros\n- [ ] Backend proxy for keys explicit" \
    "Parent #$E0" \
    "Implementation code")" \
  "Phase 0 — Infra and Docs" docs phase-0 p0

create_issue "[Docs] iOS app module architecture + TabView IA" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/ios-app.md\`: modules (App, Core, Persistence, Features, AgentClient), SwiftData ownership, TabView navigation, concurrency, DI." \
    "- [ ] Folder layout defined\n- [ ] TabView IA documented (Capy / Food Log / Library; Settings top-right)\n- [ ] iPhone-only target called out" \
    "Parent #$E0" \
    "Building screens")" \
  "Phase 0 — Infra and Docs" docs phase-0 p0

create_issue "[Docs] LangGraph harness architecture" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/harness.md\`: nodes/state, tool boundaries, memory snapshot shape, retry/abstain policy, calc_macros ownership decision." \
    "- [ ] Node graph described\n- [ ] Tools: search_food, propose_meal, calc_macros ownership decided\n- [ ] Max 2 retries then abstain documented" \
    "Parent #$E0; related #$E4" \
    "Python implementation")" \
  "Phase 0 — Infra and Docs" docs harness phase-0 p0

create_issue "[Docs] Data model document" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/data-model.md\`: Food, MealEntry, DailyTarget, Memory, Templates, reserved Inventory." \
    "- [ ] Entities and relationships listed\n- [ ] Macro snapshots on diary items\n- [ ] Inventory reserved, not exposed in V1 UI" \
    "Parent #$E0" \
    "SwiftData model code")" \
  "Phase 0 — Infra and Docs" docs data phase-0 p0

create_issue "[Docs] API contracts (Pydantic ↔ Swift Codable)" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/api-contracts.md\`: request/response schemas, auth header/ID token rules." \
    "- [ ] Meal interpretation request/response fields defined\n- [ ] USDA lookup contract defined\n- [ ] No trusted macros in API responses" \
    "Parent #$E0; blocks Phase 1 harness" \
    "Server/client codegen")" \
  "Phase 0 — Infra and Docs" docs harness phase-0 p0

create_issue "[Docs] Security + App Store privacy notes" \
  "$(body_std "docs" "—" \
    "Write \`docs/architecture/security.md\`: secrets, no client API keys, auth privacy strings." \
    "- [ ] Secrets policy clear\n- [ ] Auth privacy notes drafted\n- [ ] App Check posture linked" \
    "Parent #$E0" \
    "App Store submission")" \
  "Phase 0 — Infra and Docs" docs infra phase-0 p0

create_issue "[Docs] Local development runbook" \
  "$(body_std "docs" "—" \
    "Write \`docs/runbooks/local-dev.md\`: emulators, Xcode setup, Functions deploy placeholders." \
    "- [ ] Steps clone → run iOS → hit emulators\n- [ ] Env vars listed without secrets\n- [ ] Links to Firebase project docs" \
    "Parent #$E0" \
    "Automated CI")" \
  "Phase 0 — Infra and Docs" docs phase-0 p0

create_issue "[Docs] PRD mapping (FR-x → epic/issue)" \
  "$(body_std "docs" "—" \
    "Write \`docs/prd-mapping.md\` mapping FR-1…FR-10 and screen IA to epics/issues." \
    "- [ ] All P0 FRs mapped\n- [ ] P2 FRs marked deferred\n- [ ] Links to GitHub epics" \
    "Parent #$E0; after epics exist" \
    "New product requirements")" \
  "Phase 0 — Infra and Docs" docs phase-0 p0

create_issue "[Docs] Screen inventory — Capy / Food Log / Library / Settings" \
  "$(body_std "docs" "—" \
    "Full screen inventory with purpose, entry/exit, empty/loading/error, PRD mapping for locked TabView IA." \
    "- [ ] Auth, Onboarding, Capy, Food Log, Library, Settings documented\n- [ ] Flows: activation, correction, Log/Swap/Not this\n- [ ] Insights V1 scope decided (light vs deferred charts)\n- [ ] Copy rules + a11y notes" \
    "Parent #$E0; blocks Phase 2 UI" \
    "Implementing UI")" \
  "Phase 0 — Infra and Docs" docs design phase-0 p0

create_issue "[Design] App Color Palette + liquid-glass Material guide" \
  "$(body_std "design" "—" \
    "Define fixed App Color Palette (\`docs/design/color-palette.md\` + asset catalog names) and Material/liquid-glass usage rules." \
    "- [ ] Token names + roles documented\n- [ ] Semantic system color usage clarified\n- [ ] Liquid glass / Material rules (subtle, HIG-aligned)\n- [ ] Ban ad-hoc hex in views" \
    "Parent #$E0" \
    "Shipping final brand mascot assets")" \
  "Phase 0 — Infra and Docs" design docs phase-0 p0

create_issue "[Design] Figma — three tabs + Settings" \
  "$(body_std "design" "—" \
    "Figma or annotated wireframes for Capy, Food Log, Library, Settings before Phase 2 coding." \
    "- [ ] All three tabs + Settings covered\n- [ ] Component inventory: budget bar, chips, talk box, day switcher, library rows\n- [ ] Link in docs/design/" \
    "Parent #$E0; depends on palette + screen inventory" \
    "Pixel-perfect production illustrations")" \
  "Phase 0 — Infra and Docs" design phase-0 p0

create_issue "[Docs] Cursor rules (palette, native UI, no LLM macros)" \
  "$(body_std "docs" "—" \
    "Add \`.cursor/rules\` (and optional AGENTS.md) for TabView IA, App palette + materials, SwiftUI conventions, no LLM macros, secrets hygiene, schema doc sync." \
    "- [ ] Rules committed under \`.cursor/rules\`\n- [ ] Issue linking / commit convention noted\n- [ ] Optional Firebase/SwiftUI skill pointers" \
    "Parent #$E0" \
    "Feature implementation")" \
  "Phase 0 — Infra and Docs" docs phase-0 p0

create_issue "[Docs] Seed food / template inventory (content only)" \
  "$(body_std "docs" "—" \
    "Draft inventory of ~30 foods, Indian composites, ingredient families, 10–20 regular meal templates (JSON or spreadsheet)." \
    "- [ ] ~30 foods with aliases/families\n- [ ] Manual Indian composites listed\n- [ ] 10–20 meal templates listed\n- [ ] Content only — no importer code" \
    "Parent #$E0; feeds #$E3" \
    "Seed importer implementation")" \
  "Phase 0 — Infra and Docs" docs data phase-0 p0

# ---------- Phase 1 ----------
echo "Creating Phase 1 issues..."

create_issue "[Core] Remaining budget pure functions + clamp at zero" \
  "$(body_std "core-math" "FR-2" \
    "Pure functions for targets minus eaten per macro; clamp at zero; over-target shows 0 left with factual note." \
    "- [ ] Unit tests for remaining/clamp\n- [ ] Negative remaining never rendered\n- [ ] Display rounding does not feed calc" \
    "Parent #$E2; Phase 0 data model docs" \
    "UI chrome")" \
  "Phase 1 — Harness Core" core-math phase-1 p0

create_issue "[Core] Same-day variety filter + 7-day repetition decay" \
  "$(body_std "core-math" "FR-4, FR-5" \
    "Hard-block ingredient families logged today; soft decay for foods on 3+ of last 7 days." \
    "- [ ] Family hard filter golden cases\n- [ ] Decay ranks down not out\n- [ ] Deterministic pass/fail tests" \
    "Parent #$E2" \
    "Inventory constraints (P2)")" \
  "Phase 1 — Harness Core" core-math phase-1 p0

create_issue "[Core] Suggestion verifier ±10% all macros + abstain" \
  "$(body_std "core-math" "FR-3" \
    "Propose one meal from templates; verify calories ≤ remaining and each macro within ±10%; max 2 retries then abstain." \
    "- [ ] Verifier unit tests\n- [ ] Retry with named reasons\n- [ ] Abstention typed fallback\n- [ ] No LLM macros used" \
    "Parent #$E2; depends on remaining + variety" \
    "Pantry-constrained suggestions (P2)")" \
  "Phase 1 — Harness Core" core-math phase-1 p0

create_issue "[Data] Seed catalog importer + local food cache schema" \
  "$(body_std "data" "FR-6" \
    "Implement seed import for foods/composites/templates into local store; cache schema for search hits/misses." \
    "- [ ] Idempotent import\n- [ ] Composites marked manual\n- [ ] Same-day miss cache policy" \
    "Parent #$E3; Phase 0 seed inventory" \
    "Branded USDA noise catalog")" \
  "Phase 1 — Harness Core" data phase-1 p0

create_issue "[Data] USDA Foundation/SR Legacy fallback client" \
  "$(body_std "data" "FR-6" \
    "Server-side USDA search/map nutrients; reject incomplete records; never re-fetch miss same day in flow." \
    "- [ ] Nutrient ID mapping explicit\n- [ ] Cache accepted results\n- [ ] Keys via Secret Manager only" \
    "Parent #$E3; Phase 0 secrets runbook" \
    "Live client-side USDA calls")" \
  "Phase 1 — Harness Core" data harness phase-1 p0

create_issue "[Harness] Define LangGraph state and node graph for meal intent" \
  "$(body_std "harness" "FR-1" \
    "Implement LangGraph: intent → search → propose portions → clarify/correct." \
    "- [ ] State schema matches api-contracts.md\n- [ ] Clarifying question on ambiguous portion\n- [ ] No silent gram guesses" \
    "Parent #$E4; Phase 0 harness docs" \
    "Coach/motivation nodes")" \
  "Phase 1 — Harness Core" harness phase-1 p0

create_issue "[Harness] Gemini structured output schema for food+grams" \
  "$(body_std "harness" "FR-1" \
    "Gemini structured-output node with Pydantic validation; never emit trusted macros." \
    "- [ ] Schema validation fails closed\n- [ ] Intent, food refs, grams/ambiguity, corrections only\n- [ ] Contract tests" \
    "Parent #$E4" \
    "Free-form chat without structure")" \
  "Phase 1 — Harness Core" harness phase-1 p0

create_issue "[Harness] Tools: search_food, propose_meal, calc_macros boundary" \
  "$(body_std "harness" "FR-1, FR-3" \
    "Expose narrow tools per Phase 0 ownership decision; verify failures feed named reasons." \
    "- [ ] Tool surface documented and implemented\n- [ ] Max 2 verify retries then abstain\n- [ ] Macros from deterministic path only" \
    "Parent #$E4; #$E2" \
    "Arbitrary tool calling")" \
  "Phase 1 — Harness Core" harness phase-1 p0

create_issue "[Harness] Explicit memory snapshot contract" \
  "$(body_std "harness" "—" \
    "Pass minimal explicit memory snapshot (prefs, dislikes, allergies, regulars, corrections) per authenticated request." \
    "- [ ] Snapshot shape in api-contracts.md\n- [ ] No hidden inferred memories\n- [ ] Unit/contract coverage" \
    "Parent #$E4" \
    "Auto-inferred memories")" \
  "Phase 1 — Harness Core" harness phase-1 p0

create_issue "[Harness] Emulator runbook exercised + harness unit/contract tests" \
  "$(body_std "harness" "—" \
    "Run Auth+Functions emulators; golden parse cases for seeded foods, Indian composites, ambiguous portions." \
    "- [ ] Emulator path works locally\n- [ ] Golden parse cases pass\n- [ ] Redacted structured logs" \
    "Parent #$E4" \
    "UI tests")" \
  "Phase 1 — Harness Core" harness eval phase-1 p0

create_issue "[Both] Assistance dial policy matrix (pure policy)" \
  "$(body_std "both" "FR-7" \
    "Pure policy data for Full Assist / Guided / Quiet: initiation + benefit callouts; reactive log/suggest always on." \
    "- [ ] Quiet = zero unprompted messages\n- [ ] Full Assist benefit after every completed log\n- [ ] Unit tests for policy matrix\n- [ ] No adaptive step-up/down in V1" \
    "Parent #$E8" \
    "Local notifications; adaptive dial")" \
  "Phase 1 — Harness Core" harness ui phase-1 p0

# ---------- Phase 2 ----------
echo "Creating Phase 2 issues..."

create_issue "[UI] Auth screen — Apple and Google entry points" \
  "$(body_std "ui" "—" \
    "Auth screen with Sign in with Apple and Continue with Google via Firebase Auth." \
    "- [ ] Both providers work on simulator/device dogfood\n- [ ] Error/cancel states\n- [ ] Palette + native components" \
    "Parent #$E1; Phase 0 Firebase auth" \
    "Account linking edge cases beyond V1")" \
  "Phase 2 — UI Core" ui infra phase-2 p0

create_issue "[UI] Onboarding — targets, dial, starter preferences" \
  "$(body_std "ui" "—" \
    "Sub-two-minute onboarding seeding goals, assistance dial, starter prefs into Settings." \
    "- [ ] Completes into Main TabView\n- [ ] Values persist\n- [ ] No tutorial tour / DB tour" \
    "Parent #$E1 / #$E7B" \
    "HealthKit-derived targets")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Main TabView shell + Settings toolbar" \
  "$(body_std "ui" "—" \
    "Root TabView: Capy (default), Food Log, Library; top-trailing Settings gear on primary tabs." \
    "- [ ] Three tabs only\n- [ ] Settings pushes stack (not a tab)\n- [ ] Liquid glass / system tab bar materials\n- [ ] App palette tokens" \
    "Parent #$E5/#$E6/#$E7/#$E7B; Phase 0 screen docs" \
    "macOS/visionOS")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Capy tab — budget, pick, talk box, confirm" \
  "$(body_std "ui" "—" \
    "Agentic screen: remaining budget, one pick + reasons, Log/Swap/Not this, talk box, confirmation sheet." \
    "- [ ] Anatomy matches screen docs\n- [ ] Empty/loading/offline/abstention states\n- [ ] Editable grams on confirm\n- [ ] Copy: doer verbs, no coach language" \
    "Parent #$E5" \
    "Backend wiring (Phase 3)")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Food Log tab — goals, day switcher, insights, log" \
  "$(body_std "ui" "—" \
    "Goals summary, date switcher, meal list, Insights entry per Phase 0 Insights scope." \
    "- [ ] Day switch updates log\n- [ ] Edit/delete entries\n- [ ] Remaining recomputes instantly (local maths stub ok)\n- [ ] Insights button present per scoped V1" \
    "Parent #$E6" \
    "Heavy analytics charts if deferred")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Library tab — custom + AI-generated items" \
  "$(body_std "ui" "—" \
    "Custom Meals / Recipes / Food plus AI-generated section; CRUD; use from log or Capy." \
    "- [ ] Sections/filters work\n- [ ] Create/edit/delete\n- [ ] Source badge for AI-generated" \
    "Parent #$E7" \
    "Grocery/inventory")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Settings — goals, prefs, diets, Capy dial, user" \
  "$(body_std "ui" "—" \
    "Settings stack: Goals, Food preferences, Diets, Capy Settings (dial), User details (profile/sign-out)." \
    "- [ ] All five areas present\n- [ ] Target changes never rewrite past days\n- [ ] Explicit prefs only" \
    "Parent #$E7B" \
    "Adaptive dial auto-change")" \
  "Phase 2 — UI Core" ui phase-2 p0

create_issue "[UI] Manual food search / log from Food Log or Library" \
  "$(body_std "ui" "—" \
    "FoodNoms-like manual search/log path using local cache UI (USDA later in Phase 3)." \
    "- [ ] Search + select + grams\n- [ ] Confirm before persist\n- [ ] Palette/native List patterns" \
    "Parents #$E6/#$E7" \
    "Barcode/photo logging")" \
  "Phase 2 — UI Core" ui phase-2 p0

# ---------- Phase 3 ----------
echo "Creating Phase 3 issues..."

create_issue "[Both] Wire Capy talk box ↔ authenticated callable ↔ LangGraph" \
  "$(body_std "both" "FR-1" \
    "End-to-end authenticated requests from Capy tab to LangGraph; structured responses into confirmation UI." \
    "- [ ] ID token required\n- [ ] Clarification and confirm flows work\n- [ ] Offline/error handling" \
    "Parents #$E4/#$E5; Phase 1+2 complete" \
    "Unauthenticated public API")" \
  "Phase 3 — Integration Loop" harness ui phase-3 p0

create_issue "[Core] On-device deterministic maths as source of truth" \
  "$(body_std "core-math" "FR-2, FR-3" \
    "All displayed macros/remaining/suggestion verification computed in Swift; ignore any model numbers." \
    "- [ ] Confirm path uses Swift calc only\n- [ ] Suggestion verify on device\n- [ ] Snapshot persistence on diary items" \
    "Parent #$E2" \
    "Server-side maths as authority")" \
  "Phase 3 — Integration Loop" core-math phase-3 p0

create_issue "[UI] Confirm-before-persist logging + correction deltas" \
  "$(body_std "ui" "FR-1, FR-8" \
    "Never silent log; confirmation required; corrections recompute and show delta." \
    "- [ ] Confirm writes MealEntry\n- [ ] Correction shows delta\n- [ ] Corrections tagged as eval candidates" \
    "Parents #$E5/#$E6" \
    "Auto-log without confirm")" \
  "Phase 3 — Integration Loop" ui phase-3 p0

create_issue "[Core] Suggestion pipeline templates → variety → verify → abstain" \
  "$(body_std "core-math" "FR-3, FR-4, FR-5" \
    "Wire suggestion engine into Capy tab actions Log/Swap/Not this." \
    "- [ ] Swap re-runs verified search\n- [ ] Never free-generates macros\n- [ ] Abstain fallback copy" \
    "Parent #$E2/#$E5" \
    "Fridge inventory constraint")" \
  "Phase 3 — Integration Loop" core-math ui phase-3 p0

create_issue "[Both] Dial enforcement in-app (Full Assist / Guided / Quiet)" \
  "$(body_std "both" "FR-7" \
    "Apply policy in foreground: Quiet silence; Full Assist benefit callouts; Guided evening check-in." \
    "- [ ] Quiet eval: zero unprompted\n- [ ] Full Assist benefit after log\n- [ ] No push notifications" \
    "Parent #$E8" \
    "Local notifications")" \
  "Phase 3 — Integration Loop" harness ui phase-3 p0

create_issue "[Dogfood] First open → log → suggestion in under 2 minutes" \
  "$(body_std "both" "—" \
    "Dogfood the activation loop end-to-end on device/simulator." \
    "- [ ] Timed path < 2 minutes\n- [ ] Seeded foods resolve\n- [ ] Recorded as dogfood checklist" \
    "Integration issues above" \
    "Public launch marketing")" \
  "Phase 3 — Integration Loop" dogfood phase-3 p0

# ---------- Phase 4 ----------
echo "Creating Phase 4 issues..."

create_issue "[Eval] Golden set ≥90% + Indian composites + variety" \
  "$(body_std "eval" "—" \
    "Golden set covering variety, verifier retry/abstain, Indian composites; launch gate ≥90%." \
    "- [ ] Cases in shared JSON\n- [ ] Swift + Python compatible runners where applicable\n- [ ] ≥90% pass documented" \
    "Parent #$E9" \
    "Non-tracker user study")" \
  "Phase 4 — Polish and Evals" eval phase-4 p0

create_issue "[Eval] Dial evals: Quiet silence + Full Assist benefit + no coach vocab" \
  "$(body_std "eval" "FR-7" \
    "Hard fail unprompted Quiet messages; fail Full Assist log without benefit; fail coach vocabulary." \
    "- [ ] Automated or scripted checks\n- [ ] Copy ban list" \
    "Parent #$E9/#$E8" \
    "Adaptive dial")" \
  "Phase 4 — Polish and Evals" eval phase-4 p0

create_issue "[Eval] Zero unverified macros ship gate" \
  "$(body_std "eval" "FR-3" \
    "Structural guarantee: no macro number reaches UI unverified." \
    "- [ ] Audit path from harness response → UI\n- [ ] Test asserting rejection of model macros" \
    "Parent #$E9" \
    "—")" \
  "Phase 4 — Polish and Evals" eval phase-4 p0

create_issue "[UI] Accessibility / Dynamic Type pass on core screens" \
  "$(body_std "ui" "—" \
    "VoiceOver and Dynamic Type pass for tabs, budget, pick actions, Settings." \
    "- [ ] Labels on budget + actions\n- [ ] Large text does not clip critical actions\n- [ ] Checklist in issue" \
    "Parent #$E9" \
    "Full localization")" \
  "Phase 4 — Polish and Evals" ui phase-4 p0

create_issue "[Docs] Risk gates: name/trademark + first non-tracker test" \
  "$(body_std "docs" "—" \
    "Track open decisions: App Store/USPTO/domain; first non-tracker test gates story not build." \
    "- [ ] Checklist issue updated\n- [ ] Does not block October dogfood build" \
    "Parent #$E9" \
    "Legal counsel filing")" \
  "Phase 4 — Polish and Evals" docs phase-4 p0

# ---------- Phase 5 ----------
echo "Creating Phase 5 issues..."

create_issue "[P2] Inventory-aware picks (FR-9)" \
  "$(body_std "data" "FR-9" \
    "Constrain suggestions to stock on hand; decrement on log." \
    "- [ ] Schema uses reserved inventory table\n- [ ] No foods table migration required" \
    "Parent #$E10" \
    "V1 October ship")" \
  "Phase 5 — Post-October (P2)" data p2 phase-5

create_issue "[P2] HealthKit dynamic budgets (FR-10)" \
  "$(body_std "infra" "FR-10" \
    "Read workouts via HealthKit; training days expand budget live." \
    "- [ ] Explains +calories on screen\n- [ ] V1 budgets stay static until this ships" \
    "Parent #$E10" \
    "V1 October ship")" \
  "Phase 5 — Post-October (P2)" infra p2 phase-5

create_issue "[P2] Grocery lists from low stock" \
  "$(body_std "ui" "—" \
    "Grocery list generated from low inventory after inventory phase." \
    "- [ ] Depends on FR-9" \
    "Parent #$E10; FR-9" \
    "V1")" \
  "Phase 5 — Post-October (P2)" ui p2 phase-5

create_issue "[P2] Native workout logging (only if pulled)" \
  "$(body_std "ui" "—" \
    "Native workout logging only if users pull; merge data not apps first." \
    "- [ ] Gated on demand signal" \
    "Parent #$E10" \
    "Building a second mature app before agent")" \
  "Phase 5 — Post-October (P2)" ui p2 phase-5

create_issue "[P2] Adaptive dial step-up / step-down (propose-and-confirm)" \
  "$(body_std "both" "—" \
    "After 14 logged days offer step-down; after 3 missed Guided days offer step-up; never silent change." \
    "- [ ] Propose-and-confirm only" \
    "Parent #$E10/#$E8" \
    "V1 October")" \
  "Phase 5 — Post-October (P2)" harness ui p2 phase-5

echo "DONE. Map written to $OUT"
wc -l "$OUT"
