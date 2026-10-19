# Referee eval results

Each folder here is one real run of `python -m jahbadh.eval` against the gpt-5-mini deployment on Foundry. `report.json` is the full output and `report.md` is the same thing in plain words. We plant known-false claims (a wrong number, a wrong player, a made-up event, the wrong club, the wrong minute) into the writer's real drafts, and the Referee checks them alongside the real claims. A planted claim counts as caught when the Referee rejects it on its first check, and it is always thrown away afterwards, never rewritten or published. The files are untouched output and never edited by hand. If a run is ever repeated, both runs stay here.

The 20-match run was made with:

```bash
python -m jahbadh.eval --seeds 1-20 --plants 50 --out data/eval/2026-10-19-referee
```
