# Jahbadh design doc

Started 17 Oct 2026. This is my entry for the Microsoft x Premier League "Inside the Game" hackathon, challenge: **Synthetic Match Insights Engine for Premier League Studio**. Submissions close 27 Oct, 11:59 PM PT.

Jahbadh (جهبذ) is an Arabic word for someone who really knows their stuff. I picked it because the project has to understand three things at once: simulation, tactics and writing.

## What I'm building

Jahbadh is a match desk run by AI agents. It watches a synthetic football match live and produces commentary, tactical breakdowns, heatmaps and a full-time recap. You can switch languages, and you can switch who it's written for.

The part I care about most is that every claim has to be backed by the data. If the desk says "they've overloaded the left flank since the 60th minute", you can click that sentence and see the events and numbers behind it. If one of the writing agents makes something up, a Referee agent catches it and sends it back. I'm also showing the rejected drafts in the UI on purpose, so you can see the checking actually happening.

## Why

Studios and streaming platforms want match content fast and in lots of languages, and LLMs can write it in seconds. The problem is that in football one confident wrong sentence on air is embarrassing, and people stop trusting the output.

Everyone in this challenge is building some kind of insights engine, and most of them will generate recaps. I want mine to stand out on two things:

1. **Trust.** Every claim is grounded and you can check it.
2. **Actual tactics.** The numbers (heatmaps, shape, pressing, overloads) are computed from positional data in Python. The LLM explains them but doesn't invent them.

## What a good demo looks like

- A synthetic match is playing on the desk.
- Something tactical happens, like a team switching to a back three at 60'.
- A few seconds later the desk explains it, for example: "Since going to a back three, Rivermouth have been overloading the left 4v2, and that's where the 64' chance came from."
- I click the sentence and the sub, the pass chain, the shot and the overload metric light up.
- A rejected draft shows up with the reason it got rejected.
- I switch to Arabic or Spanish, or from "studio pundit" to "casual fan".
- Full time hits and a grounded recap appears.

If someone watching the 2-minute video gets all of that, I'm happy.

## Goals

- A synthetic data generator that makes full matches with **events and tracking data** (player positions over time)
- A Python tactical analytics library that does all the maths
- A multi-agent pipeline on the Microsoft stack: analyst, tactical, writers, referee, localization and persona agents
- Grounding on every claim, plus a way to measure how well it works
- A clean live desk UI, deployed somewhere judges can use it
- Proper engineering: typed schemas, tests, a clear structure and a decent README

## Not doing

- Real Premier League data, real players or club badges. Everything is made up. The rules want synthetic data anyway, and it keeps me away from IP issues.
- Video or computer vision
- A physics-accurate simulation. "Football-realistic" means the stats and movement look believable, not that it's a game engine.
- Logins or user accounts

## What would make this a fail even if it technically works

- The text reads well but it's wrong
- The tactics panel is really just the LLM guessing
- The demo crashes, lags or burns through my Azure credit during judging
- Loads of half-finished features and nothing polished

## Constraints

- I'm solo, with about 10 days (17 to 27 Oct). I want it ready by the 26th so I have a buffer day.
- I've got $100 of Azure for Students credit. That has to cover building it and keeping the demo up until judging ends on 10 Nov.
- The backend is all Python, because that's what I'm strongest in.
- Submission needs a public GitHub repo, a demo video under 2 minutes, a working link for judges and everything in English.
- I'm doing small commits that each make sense on their own, not giant dumps.

## How it lines up with judging

Each criterion is 20%:

- **Technical implementation:** Microsoft Foundry models, Microsoft Agent Framework, Azure Container Apps and Azure AI Translator. Most of these are on the rules' "hero technologies" list.
- **Agentic design:** agents with one job each, tool use for the analytics, and a Referee loop that rejects and rewrites.
- **Real-world impact:** trustworthy, multilingual content for studios and streamers.
- **UX and presentation:** the live desk, click-to-evidence, tactical visuals and a tight video.
- **Category fit:** I'm going for **Best Multi-Agent System** and **Best Use of Microsoft Foundry**. Azure Cloud-Native would be a bonus.

## Architecture

How data flows:

1. The **simulator** generates a match (events + tracking) and saves it.
2. The **analytics library** reads the match and computes metrics. Every metric gets an ID and remembers which events or frames it came from.
3. The **agents** run: Analyst, then Tactical, then Writers, then Referee (rewrite if needed), then Persona, then Localization.
4. **FastAPI** streams the approved feed and match state to the browser over Server-Sent Events.
5. The **live desk UI** shows everything.

Matches replay sped up (e.g. 90 minutes in about 15), so you can see "live" without waiting a full game.

## The parts

### Simulator

- Two made-up teams, 11 players each plus subs. Each team has tactical settings: formation, how high they press, width, tempo and how direct they play.
- It outputs two linked things:
  - **Event log**, about 1,500 to 2,000 events per match: passes, carries, shots with xG, tackles, interceptions, presses, fouls, cards, subs, goals and formation changes. Each event has an ID, time, team, player, start and end x/y, and outcome.
  - **Tracking frames** at about 1 per second, with x/y for all 22 players and the ball. That's roughly 120k rows per match, and it's what makes heatmaps possible.
- Players drift toward their formation spot, which shifts depending on where the ball is and whether their team has it, plus some randomness. Events come from a possession state machine where the odds depend on zone, pressure and the team settings.
- **Storyline knobs** let me script moments for the demo (like a sub at 60' that changes the formation) while the rest stays random.
- It's seeded, so the same seed always gives the same match. That matters for tests and for a demo that doesn't surprise me.
- Matches can be exported as a standalone dataset (Parquet + JSON schema), which also covers the "expand datasets" theme.
- A realism test checks that passes, shots, xG and pass completion land in normal top-flight ranges.

### Tactical analytics

Plain pandas and numpy, with no LLM involved. Every result is a metric object with an ID, value, time window, team or player, and the event or frame IDs it was built from.

Must have:
- xG per shot and cumulative
- PPDA (pressing intensity)
- Field tilt (who's dominating territory)
- Momentum (rolling threat or xG)
- Zone overloads (attackers vs defenders per zone)
- Heatmaps per player or team, for any time window
- Team shape: average positions, defensive line height, compactness, width
- Before/after comparisons around a moment, like a sub or formation change
- Pass networks

Nice to have if there's time: automatic movement pattern detection (overlapping fullbacks, a striker dropping deep, repeated runs). Only once the core is solid.

### Agents

Each agent has one job, a typed input and output, and only the tools it needs.

- **Analyst:** watches the events and flags key moments (goals, big chances, momentum swings, tactical changes). Tools: event queries, momentum, xG.
- **Tactical:** explains why things are happening using the computed metrics. Tools: the full analytics library.
- **Writers** (commentary, recap, highlights): turn findings into text in a given voice. Output is structured: the text plus a list of claims, each with evidence IDs. They don't get tools and only work from what Analyst and Tactical give them.
- **Referee:** checks every claim and approves it, rejects it or sends it back with a reason.
- **Persona:** rewrites approved content for a studio pundit, casual fan or fantasy player, without adding new facts.
- **Localization:** translates with Azure AI Translator and an LLM polish pass so the football terms come out right.

**How the Referee checks a claim:**
1. **Deterministic check:** the evidence IDs have to exist, and any number in the text has to match the computed metric (within a tolerance). There's no LLM in this step, so it's fast, cheap and can't be argued with.
2. **Semantic check:** an LLM judge confirms the evidence really supports the sentence.
3. If a claim fails, it's rejected with a reason and the writer gets one retry. If the retry fails too, the claim is dropped. Rejections are saved and shown in the UI.
4. Persona output gets re-checked, so no new claims sneak in.

**Order:** Referee, then Persona (still in English, re-checked), then Localization last. Translations keep the same claim IDs and evidence. After translating I only run the deterministic check (numbers and IDs survived), so I never need an LLM judge reading Arabic or Spanish.

**Language/persona switching:** generated the first time someone picks a combo, then cached. For the showcase matches I'll generate all 9 combos (3 languages x 3 personas) ahead of time, so switching is instant.

### Pacing

- The LLM pipeline only runs on moments the Analyst flags: goals, big chances, cards, subs and formation changes, momentum swings, plus a tactical check-in roughly every 10 match minutes. That's about 15 to 30 moments per match.
- Normal events like routine passes and throw-ins get short template lines. No LLM, no cost.
- Live mode runs at about 6x speed with a "skip to next moment" button. The feed can lag the clock by a few seconds, and the UI shows "the desk is thinking..." while that happens. Moments are processed concurrently, and each feed item is stamped with its match minute.
- Replay mode can run at any speed because it's all precomputed.

### Orchestration

- Microsoft Agent Framework (Python) on Microsoft Foundry model deployments.
- Event-driven: when the Analyst flags something, the flow is Tactical, Writers, Referee, Persona, then Localization.
- Tracing through Foundry or Application Insights, so I can show the agent traces in the README and the video.

### API and UI

- FastAPI backend, streaming over Server-Sent Events
- Live desk layout, based on my first mockup:
  - **Left:** event stream
  - **Middle:** tactical view, with the pitch, shape, overload zones, pass chains, heatmaps, metric tiles and momentum bar
  - **Right:** agent feed, with "Verified" badges, click-to-evidence and the rejected drafts
  - **Top bar:** score, minute, persona switch, language switch (at least EN, AR and ES)
  - Full-time recap button
- Clicking a claim highlights its events on the left and its metric on the pitch.
- The mockup is at `.superpowers/brainstorm/617-1792227804/content/desk-layout.html`. It's gitignored, so I'll copy it into `docs/` if I want it in the repo.

### Evaluation

A script that runs a bunch of seeded matches through the pipeline and reports:
- **First-draft pass rate:** how many writer drafts pass the Referee without changes. This is the honest number for how good the writers are.
- **Catch rate:** I plant known-false claims (wrong numbers, wrong players, fake events) and measure how many the Referee catches. Just reporting "% of published claims grounded" would be 100% by design, which doesn't prove anything.
- Rejection rate and the reasons
- Whether numbers in the text match the computed values
- Latency per moment

The results go in the README. Something like "the Referee caught 47 of 50 planted false claims across 20 matches" is the kind of line I want in the video.

## Tech stack

- **Language:** Python 3.12
- **Sim + analytics:** numpy, pandas, pydantic
- **Storage:** Parquet + SQLite locally. I'll only add a managed Azure store if I need one.
- **Models:** Microsoft Foundry deployments, a small cheap model (gpt-4o-mini class) for most agents
- **Orchestration:** Microsoft Agent Framework
- **Translation:** Azure AI Translator (free tier)
- **API:** FastAPI + SSE
- **Frontend:** React + Vite + TypeScript, built to static files and served by FastAPI. I picked this over Streamlit because UX is 20% of the score.
- **Hosting:** Azure Container Apps (consumption plan, scales to zero)
- **CI/CD:** GitHub Actions to run tests on every push and deploy from main
- **Tests:** pytest

## Keeping the demo alive and cheap

Judges need it working until 10 Nov, so this matters as much as features.

- **Replay mode** is the default for judges. It streams pre-generated, already-checked agent output for a few showcase matches. It's free, instant and won't break.
- **Live mode** is a "run a fresh match" button that really calls the agents. It's rate limited (a few runs an hour) so nobody can drain my credit.
- **Showcase matches are real pipeline output.** I can pick the best seeds, but I won't hand-edit the text. The UI and README will say clearly that replay mode is precomputed.
- **Fallback:** if Foundry or Agent Framework causes problems, I'll call the model deployments directly through the Python SDK behind my own small agent interface. The agent contracts stay the same, so nothing else has to change.
- Container Apps scales to zero, so it costs basically nothing when nobody's using it.
- Azure budget alerts at $50 and $80.

## Engineering practices

- Package layout: `simulator/`, `analytics/`, `agents/`, `api/`, `web/`, `eval/`
- Pydantic schemas for events, frames, metrics and claims. These are the contracts between the parts.
- Tests: simulator determinism and realism, metric correctness on tiny hand-made scenarios, Referee accept and reject cases, and API smoke tests.
- No secrets in the repo: `.env` locally, `.env.example` committed, real values in Azure settings.
- `.gitignore` covers `.superpowers/`, `.env`, generated data and build folders.
- Small, meaningful commits as I go.
- The README gets the architecture diagram, setup steps, eval results, agent traces and screenshots.

## Rough 10-day plan

| Day | Date | Focus |
|---|---|---|
| 1 | 17 to 18 Oct | Repo setup, schemas, simulator v1 (events) |
| 2 | 19 Oct | Simulator v2 (tracking, storyline knobs, realism tests) |
| 3 | 20 Oct | Analytics core + tests (xG, PPDA, tilt, shape, heatmaps) |
| 4 | 21 Oct | Foundry setup, Analyst and Tactical agents with tools |
| 5 | 22 Oct | Writers + Referee and the grounding loop |
| 6 | 23 Oct | Orchestration, API, live SSE stream |
| 7 | 24 Oct | Live desk UI |
| 8 | 25 Oct | Localization, personas, recap, eval script |
| 9 | 26 Oct | Azure deploy, replay mode, README, diagrams. **Ready to submit.** |
| 10 | 27 Oct | Demo video, submission text, buffer |

I'll break each day down into proper tasks in a separate plan.

## Still flexible

- Exact simulator probabilities and movement model, as long as the realism tests pass
- Prompt wording for each agent
- Visual styling, as long as it keeps the mockup layout
- Exact metric formulas, where there's a standard definition
- Tracking at about 1 Hz and the replay speeds, which I can tweak once I see how it feels
