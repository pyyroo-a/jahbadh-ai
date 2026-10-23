# Submission: Jahbadh

**Challenge:** Synthetic Match Insights Engine for Premier League Studio

**Live demo:** https://ca-jahbadh.nicesand-4113ef71.uaenorth.azurecontainerapps.io (opens straight into a replay, no sign-in)

**Code:** https://github.com/pyyroo-a/jahbadh-ai

**Demo video (1:56):** https://youtu.be/UXhl4mRMxi8

## In one line

Jahbadh is a match desk run by AI agents that explains a football match as it happens, and proves every word: a Referee agent checks each claim against the data before anyone sees it, and you can click any sentence to see its evidence.

## What it does

A synthetic match simulator plays a full 90 minutes with events and 1 Hz tracking for every player. A pure Python analytics library turns that into metrics (xG, PPDA, field tilt, momentum, heatmaps, pass networks, overloads, player impact), and every result carries the event ids and tracking frames it came from. At each key moment, a team of agents built on Microsoft Agent Framework writes about it: an Analyst and a Tactical agent call the analytics as tools, a Writer turns their findings into one-sentence claims tagged with their evidence, and a Referee checks every claim, first with plain Python (ids, numbers at the precision written, minutes) and then with an LLM judge (meaning, causes, names). Failed claims go back once with reasons, and a failed rewrite is dropped. Approved lines are rewritten for a casual fan or a fantasy player and translated into Arabic and Spanish with Azure AI Translator, and each version is checked again.

The desk shows all of it: three layouts (studio pundit, casual fan, fantasy player watch) plus a phone view, a tactical pitch where any clicked sentence shows its events and metrics, a replay of how each goal was built (every pass and carry as an arrow, in order), a broadcast overlay cue feed, a live mode that slows the match to real time at each key moment until the checked line lands, and an ingest API so an outside feed can drive the desk.

## How well it works

From the committed eval (`data/eval/2026-10-19-referee/report.md`): The Referee caught 47 of 47 planted false claims across 20 matches. Real first drafts that passed the Referee unchanged: 196 of 442 (44%). All 336 of 336 published claims still pass the number check, and a key moment takes 51.3 seconds on average. The same eval is uploaded to the Foundry project as an evaluation run.

## Microsoft and Azure

Microsoft Foundry (`gpt-5-mini`, default content filters on), Microsoft Agent Framework workflows, Azure AI Translator, Azure Container Apps, managed identity with no keys in the container, Application Insights with Foundry's Tracing page, a Foundry evaluation run, Bicep with the Azure Developer CLI, GitHub Actions for CI and one-click deploys with a federated identity, and budget alerts. The demo video's narration is generated with Azure AI Speech (`en-GB-RyanNeural`), over a real live run recorded on the deployed site.

## Scope, honestly

- No video auto-eventing. There's no video feed anywhere in Jahbadh. Every event comes from the synthetic match simulator (or an outside feed that sends events), so nothing is detected from pictures.
- Some numbers come from the simulator's own models, and they're labelled that way. Shot speed, pass speed, the pass success odds (and the pass difficulty built from them) and everything tracking-based are synthetic, and they carry a *Simulated* tag.
- Every club and player is fictional, and the showcase replay is real, unedited output, misses included.
