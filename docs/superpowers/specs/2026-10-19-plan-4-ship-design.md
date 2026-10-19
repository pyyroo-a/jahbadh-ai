# Jahbadh Plan 4 design: ship it

Written 19 Oct 2026, after Plans 1, 2 and 3 were done, reviewed and committed (last commit `968f6ff`). This builds on the main design doc (`2026-10-17-jahbadh-design.md`) and Plan 3 (`docs/superpowers/plans/2026-10-18-plan-3-desk.md`). Everything here was talked through with the user on 19 Oct. Anything marked **(builder's call)** is a sensible default the builder can settle; everything else is the user's decision as stated.

## Intent

Plan 4 turns a working local desk into something judges can open, trust and enjoy, on a phone or a laptop, and something the video can show off. Three things matter most:

1. **Proof.** Honest numbers on how well the Referee works (planted false claims caught, first-draft pass rate, latency), measured and never tuned to look good.
2. **A desk that feels made for you.** Each persona gets its own layout, and the phone gets a proper layout of its own, because fans watch on phones.
3. **Microsoft all the way.** Foundry, Agent Framework, Translator, Container Apps, managed identity, Application Insights, Bicep with the Azure Developer CLI, GitHub Actions and budget alerts. The user wants the most out of the Microsoft stack for the category prizes (Best Use of Foundry, Best Enterprise Solution, Best Multi-Agent System, Best Azure Cloud-Native Integration), while staying cheap.

## Goals

- Three persona layouts (casual: Fan, pundit: Analyst, fantasy: Player watch) on desktop and phone.
- An ingest endpoint so outside synthetic events can drive the desk as they happen.
- Ball speed beyond shots, labelled synthetic.
- An eval across 20 seeded matches with about 50 planted false claims.
- Deployed on Azure Container Apps with no API keys in the cloud, rebuilt by one command, tested and deployed by GitHub Actions, traced into Foundry, with budget alerts.
- README with real eval numbers, a deploy guide, a video script and the submission text.

## Not doing

- Video auto-eventing (no video feed, the README already says so).
- Made-up fantasy points. Real fantasy games each have their own scoring, and inventing one would be a number the match never produced.
- Logins, accounts, real clubs or players.
- Changing the showcase `desk.json`. It stays real, unedited output, misses included.
- Optional Task 17 (simulator realism) stays parked.

## What would make this a fail even if it works

- Eval numbers that look great because the test was made easy, or a Referee that "catches" everything because it rejects everything.
- The phone layout is still overwhelming, or the pitch looks lopsided.
- A judge's first visit hangs, or someone drains the credit through live mode or ingest.
- Any paid Azure or model step run without the user's yes.
- A synthetic number shown without its "Simulated" label.

## Constraints

- Every Plan 3 Global Constraint still holds: unit tests never call Azure, SSE tests read streams that end, unique test basenames, broadcast minutes, no future leakage in live mode, replay is honest, cost guardrails, simulator changes never change a match (the fingerprint test pins seeds 42, 1 and 7), synthetic is labelled synthetic, data-true, friendly copy with no em dashes, the user commits every change.
- **The browser never computes a football number.** Anything a new layout shows (player tables, ball speed, team numbers) comes from the server.
- **Money:** the user has $98.11 of Azure credit on 19 Oct. Any model call or Azure resource that costs money needs the user's yes first, with the expected cost stated. The user runs every Azure create command themselves from step-by-step instructions.
- **Regions:** only germanywestcentral, austriaeast, uaenorth, polandcentral, centralindia. Use UAE North (where Foundry is), Germany West Central as the fallback.
- Deadline: ready by 26 Oct, submissions close 27 Oct 11:59 PM PT, the demo must stay up until judging ends on 10 Nov.

## The parts

### 1. Persona layouts

The persona switch (pundit, casual, fantasy) now changes the layout as well as the words. The language switch is unchanged. The user approved all three layouts from mockups on 19 Oct (kept in `.superpowers/brainstorm/864-1792429037/content/`, gitignored).

**Casual: Fan view (calm).**
- Desktop: today's desk, calmer. The pitch, the feed and the highlights stay; fewer numbers on screen; rejected drafts stay folded **(builder's call on exactly which tiles drop)**.
- Phone: score and minute on one line, persona and language switches in a small row underneath, a swipeable highlights strip, a thin momentum bar, the tactical view folded into one card you tap to open, then one "What's happening" feed with desk lines as big cards and events as small grey lines woven between them.

**Pundit: Analyst view (dense).**
- Left: a side-by-side numbers table for both clubs (xG, PPDA, field tilt, momentum, pass difficulty, shots, game rhythm, plus anything else the stream already carries), a small line chart per number across the match (xG, momentum, game rhythm at least), and a Referee box for this match: drafts checked, how many passed first time and the rejection reasons.
- Middle: the pitch with its layers (shapes, heatmap, pass network, shot map) and the metric tiles.
- Right: the desk feed with every number in a line highlighted, the cited metrics named on each card, and rejected drafts open by default.
- Phone: the same pieces stacked (score, highlights, numbers table, feed, tactical card folded) **(builder's call on the order below the highlights)**.

**Fantasy: Player watch.**
- Left: a table of players sortable by any column: xGI, goals, assists, shots, ball wins, cards, minutes (all from `player_impact` and the events). The three spotlight picks sit underneath as chips.
- Middle: click a player to follow them (today's follow mode). The pitch shows their smoothed heatmap with xG, distance and top speed under it, the running numbers tagged "Simulated".
- Right: desk lines about the followed players come first.
- Phone: the table becomes a swipeable row of player cards; tap one to follow.
- The player table needs a new server endpoint that gives every player's numbers up to the current clock (replay and live, no future leakage).

**Shared rules for all layouts.**
- The pitch keeps the real 105 by 68 proportions, sits centred, and both halves are the same width. Columns around it are evenly spaced. Nothing looks lopsided at any width.
- Heatmaps are smoothed when drawn. The numbers underneath stay exactly the same (21 by 14 grid).
- When a desk line is selected, a "Back to the overview" link shows above the pitch, and switching persona or mode clears the selection.
- Phone means under 768 px wide **(builder's call on the exact breakpoints)**. Tiles and the overlay lower-thirds are sized for phones. At 375 px nothing overflows: the full club names may shorten to their short codes.
- The default persona stays pundit **(builder's call)**.

### 2. Being honest about speed

Template lines arrive instantly. Agent lines land one to two minutes after a moment (about 100 s per moment in the showcase run). The UI says so plainly in one short line near the feed in live and ingest mode, and the README says so too **(builder proposes the exact copy to the user)**. The eval measures it.

### 3. Ball speed

- A synthetic ball speed for passes, worked out from each pass's length and the time until the next event, computed the same way every time. Shots keep their existing synthetic shot speed.
- First check what the simulator records (pass start and end points, the time of the next event). If the data can't support an honest number, report that to the user before building anything.
- It must not change any match: the fingerprint test for seeds 42, 1 and 7 still passes.
- Labelled "Simulated" wherever it shows: Player watch and the follow panel (a player's average and fastest pass), the Analyst numbers, and the overlay cue feed with `synthetic: true` **(builder's call on the exact spots)**. The agents' tools are not changed, so the showcase stays consistent.

### 4. Ingest

The brief asks the system to "ingest synthetic match events as they happen". The user wants this to really work live.

- New endpoints: create an ingest match with its two team sheets, then post events into it one at a time or in small batches, in our existing `Event` schema, in time order. Tracking frames are optional; without them the tracking-based layers read "no data".
- The desk plays an ingest match like a live match: the stream, template lines, stats and pitch update as each event arrives, for free. Key moments are found as the events come in (key kinds only, as in live mode) and wake the agents under the same 3-a-day live limit, which is only available when `JAHBADH_LIVE_MODE=on`. Without live mode, ingest still works with template lines and stats only.
- Guarded so strangers can't spam the public site: ingest is off unless `JAHBADH_INGEST_TOKEN` is set, and every ingest call must carry that token **(builder's call)**. Only one ingest match at a time, sharing the live run's single-run rule.
- **The clock and the end (builder's call, agreed 19 Oct):** in an ingest match "now" is the time on the latest event received. The match ends on a full-time event or an explicit close call. Like live mode, the agents stop if nobody has watched for 60 s.
- A small feeder (a script, also usable from the server) sends a simulated match into the ingest endpoint in real time, over the public HTTP door with the token, exactly like an outside system would.
- **A "Watch an outside feed" button (19 Oct, the user asked for a recommendation and agreed to it):** judges can see ingest working on the deployed link. It starts the feeder on a fresh seed, and the desk shows that ingest match. The UI is honest that the events come from our demo feeder through the ingest API. It shares the single-run rule with live mode, and if the agents wake for its key moments they use the same 3-a-day limit; with none left it still plays with template lines and stats. The button shows only when ingest is on.
- The UI shows an ingest match with its own badge ("Ingest · events from an outside feed") **(builder proposes the copy)**.

### 5. Eval

- 20 seeded matches (seeds 1 to 20 without the demo storyline, so it isn't just the showcase) **(builder's call on the seeds)**, key moments only, pundit in English.
- About 50 planted false claims spread across them, roughly ten each of: a wrong number, a wrong player, a made-up event, the wrong team, the wrong minute. They are put into the writer's drafts so they go through both Referee layers exactly like a real draft. **Caught** means the Referee rejects it on its first check. A planted claim is then dropped, never sent back for a rewrite, so the number measures the Referee alone and costs less **(builder's call, agreed 19 Oct)**.
- Reports: the catch rate (planted claims rejected), the first-draft pass rate (real drafts that pass unchanged, so a reject-everything Referee can't look good), rejection rate and reasons, whether every number in the published text matches the computed value, and latency per moment.
- Also counted, as they are: the known misses in the showcase listed in Plan 3's "After Plan 3".
- A free version with scripted fake agents runs in tests and CI. The real run costs roughly $6 to $10 and happens only after the user's yes. Before it, one pilot match measures the real cost.
- Results go in the README and the video. Never re-run to get a nicer number; if a run is repeated, both runs are reported.
- The eval results are also uploaded to the Foundry project's Evaluation page using our own code-based checks, with no extra model cost. **Verify first** that the Azure AI Evaluation SDK can upload custom results; if not, the README carries them alone.

### 6. Azure and Microsoft

- **Container Apps** in UAE North (Germany West Central if Container Apps isn't offered there), consumption plan, at most one replica (the live run and the daily counter live in the app).
  - **Always one copy running for judging (user, 19 Oct),** so a judge never waits for a cold start. Scale to zero while building, then `minReplicas: 1` from the day the link is submitted until 10 Nov. Size 0.5 vCPU and 1 GiB unless the pilot shows it's too small.
  - Measured price list for UAE North (19 Oct): idle CPU $0.000003 per vCPU-second, memory $0.000003 per GiB-second, active CPU $0.000024 per vCPU-second, with 180,000 vCPU-seconds and 360,000 GiB-seconds free each month. Always on from 25 Oct to 10 Nov at 0.5 vCPU and 1 GiB is about $3.40 idle, plus a few cents an hour while people watch. At 1 vCPU and 2 GiB it's about $10.
  - The environment must stay consumption only, so no hourly environment or dedicated-plan management fee applies. The builder checks this against the price list before the user creates it.
  - Measure the cold start anyway and report it.
- **Azure Container Registry Basic** (about $4 until 10 Nov) for the image.
- **Azure Files** mounted at `JAHBADH_STATE_DIR`, so the daily live counter survives restarts.
- **No keys in the cloud:** the container app has a managed identity that signs in to Foundry and the registry. Translator too, if it allows it without extra setup; if Translator needs a custom domain for that, its key goes in a Container Apps secret and the README says why. Local development keeps using `.env`. If the subscription won't allow the role assignments the identity needs, the Foundry key goes in a Container Apps secret instead and the README says so plainly **(builder's call, agreed 19 Oct)**.
- **Existing resources stay put:** the Bicep points at the existing Foundry project, the `gpt-5-mini` deployment and the Translator resource (`existing` references) and never creates or deletes a model deployment, so `azd up` and `azd down` can't touch the quota or the model **(builder's call, agreed 19 Oct)**.
- **Application Insights**, connected to the Foundry project, receives Agent Framework's built-in OpenTelemetry traces, so every agent call shows up in Foundry's Tracing page. Tracing is off when no connection string is set. Stays within the free 5 GB a month.
- **Bicep with the Azure Developer CLI:** every resource above, plus the budget alerts, as code. `azd up` recreates it all.
- **Budget alerts** at $50 and $80 (if the student subscription doesn't allow a budget from Bicep, the guide gives the portal clicks).
- **GitHub Actions:** on every push, pytest and the web tests, build and lint (`npm ci --prefix web`). **Deploying waits for one click (user, 19 Oct):** a "Deploy" workflow the user runs by hand from the Actions tab, which runs the tests again, builds the image and deploys. A commit on main never changes the live demo by itself. It signs in with a federated credential (no stored password). If the university tenant blocks app registrations, use a user-assigned managed identity's federated credential; if that is blocked too, the user deploys by hand with one command.
- **Content safety:** the deployment's default Foundry content filters are on; the README says so.
- **`docs/deploy.md`:** a step-by-step guide. Every step that creates something in Azure is a numbered instruction for the user to run, with the exact command or portal clicks, what it costs, what they should see, and how to check it worked.

### 7. Deferred minors

From Plan 3: run `match_timeline` in a thread at a live start (about 1.4 s stall); log a warning with the path when the live counter file is corrupt; the right message when addCombo fails after full time; the follow panel's spotlight refreshes the live count; the "Match stats 7" tile names its unit (shots). From Plan 2: duplicate judge verdicts, metric_id truncation.

### 8. README, video, submission

- README: the eval numbers, an architecture diagram, real traces, screenshots of all three layouts and the phone, the deploy guide link, the speed note, the scope note, the synthetic labels, a CI badge.
- A video script under 2 minutes that quotes only real computed numbers. The user records it.
- The submission text, repeating the README's scope note.

## Order

1. Ship basics: deferred minors, the eval (free version first, then the paid run on a yes), CI.
2. The layouts and the phone, the shared pitch and heatmap rules, item 7, the speed note.
3. Ball speed, then ingest.
4. Azure: Bicep, managed identity, tracing, the deploy guide, budgets, GitHub deploy. The deployed link is shared only after the phone layout is in.
5. README, video script, submission text.

## Cost

| Item | Rough cost | Needs a yes |
|---|---|---|
| Eval pilot (1 match) then 20 matches | under $1, then $6 to $10 | yes |
| A first real live run on the deploy | about $0.50 | yes |
| Container Registry Basic to 10 Nov | about $4 | yes (user runs it) |
| Container Apps always on 25 Oct to 10 Nov (0.5 vCPU, 1 GiB) | about $3.40 idle plus cents while watched | yes (user runs it) |
| Azure Files, Application Insights, budgets | close to free | yes (user runs it) |
| Live mode and the ingest button left on until 10 Nov | worst case about $33 (they share the 3 a day), likely far less | covered by the $50 alert |

The repo `pyyroo-a/jahbadh-ai` is made public before submitting, once the README is polished **(builder's call on when; the user flips it)**.

## Left to the builder

Exact breakpoints, tile choices in the Fan view, the order of the stacked phone panels, the ingest token mechanism, eval seeds, smoothing technique, the exact spots ball speed shows, and the Bicep layout, as marked above. Any copy the user will read on screen is proposed to the user before it lands.
