# Jahbadh (جهبذ)

**AI match intelligence you can actually trust.**

Jahbadh is my entry for the Microsoft x Premier League *Inside the Game* developer hackathon (challenge: Synthetic Match Insights Engine for Premier League Studio). It's a match desk run by AI agents that watches a synthetic football match and explains it: live commentary, tactical breakdowns, heatmaps and recaps. The twist is that every claim has to be backed by the data, and you can click any sentence to see the events and numbers behind it.

*Jahbadh* is an Arabic word for someone who truly masters a craft. Here that means understanding simulation, tactics and writing all at once.

> 🚧 Work in progress. The data foundation (simulator + tactical analytics) is done. The agents, the live desk UI and the Azure deployment are coming next.

## What's working so far

**A synthetic match simulator.** It plays a full 90-minute match one second at a time, with fictional teams and players (no real clubs or players anywhere). Every match gives you:
- about 1,500 events: passes, shots with xG, tackles, interceptions, pressure, fouls, cards, subs, goals
- 1 Hz tracking data for all 22 players and the ball (about 124,000 rows)
- scripted tactical moments for demos, like a formation switch on the hour (61' on the match clock)
- realistic numbers, checked by tests: about 850 passes at 79%, 30 shots, 3 xG, PPDA in real-world ranges
- reproducibility: same seed, same match, every time

**A tactical analytics library.** Pure Python, no AI guessing. Every result carries the evidence it was computed from (event IDs and tracking frames), so an agent can never make up a number:
- xG totals and timelines, field tilt, PPDA (pressing intensity), momentum
- heatmaps, average positions, team shape (width, length, defensive line)
- zone overloads, pass networks, midfield control
- player impact (expected goal involvement, progressive passes, ball wins and more) with rankings
- before/after comparisons around any moment

## Try it

You need Python 3.13.

```bash
py -3.13 -m venv .venv
.venv\Scripts\pip install -e .[dev]
```

Generate the demo match (seed 42 with the scripted storyline):

```bash
.venv\Scripts\python -m jahbadh.simulator --seed 42 --demo-storyline
```

Draw preview charts for it (heatmaps before and after the formation switch, average positions and momentum):

```bash
.venv\Scripts\python scripts\preview_match.py data\generated\match-042 --out previews
```

Run the tests:

```bash
.venv\Scripts\python -m pytest -q
```

The full suite takes about 2.5 minutes, because some realism checks simulate dozens of matches. One test is a known, documented gap and shows up as an expected failure (xfail).

## The data

Everything is synthetic and football-realistic. The schema and coordinate system are documented in the dataset README written by `export_schema()` in `src/jahbadh/simulator/io.py`. In short, the pitch is 105 x 68 m, the home team always attacks toward x = 105, and a match is exactly 90 minutes.

## Project docs

- Design: `docs/superpowers/specs/2026-10-17-jahbadh-design.md`
- Build plan: `docs/superpowers/plans/2026-10-17-plan-1-data-foundation.md`
