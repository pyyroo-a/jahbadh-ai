# Demo video script

Under two minutes, recorded from the live site (replay is free; shot 9 needs one live run, about $0.35). Every number is quoted from `data/eval/2026-10-19-referee/report.json` or the showcase. Speak calmly: about 2.5 words a second fits the timings.

**Before recording:** open the live desk at 1440 x 900, Studio pundit, English, 6x. Have the README's eval section open in a second tab, and Foundry's Tracing page in a third.

| # | Seconds | On screen | Voice |
|---|---|---|---|
| 1 | 7 | The desk opens and starts playing at 6x. | This is Jahbadh: a football match desk run by AI agents, where every sentence has to prove itself. |
| 2 | 11 | The event stream fills; the desk feed shows "The desk is thinking about...", then a checked line lands. | A synthetic match plays. At each key moment, agents on Microsoft Agent Framework and Foundry write about it, and a Referee agent checks every claim. |
| 3 | 13 | Click "By 42' Quill had contributed xG 1.903...". The pitch shows the shot and the goal; the tiles show xG involvement 1.91 and xG 2.88. | Click any sentence and the pitch shows why it's true: the events it cites and the metrics behind it. Python computes every number. The agents only explain them. |
| 4 | 12 | Open "Show rejected drafts" under a moment: a struck-through draft with the Referee's reason. | The Referee checks numbers with plain Python, then meaning with an LLM judge. A failed draft goes back once. If it fails again, it's dropped, and you can see why. |
| 5 | 16 | Back to the overview. Tap the "42' Quill" chip: the ten arrows draw one after another, then the gold shot. | When a goal goes in, the desk replays how it was built. Quill's goal: ten steps, from a pass in his own half, through a free kick, to the finish. Every arrow is a real event. |
| 6 | 11 | Switch to Casual fan, then AR: the lines change voice and language. | Pick who you are: studio pundit, casual fan or fantasy player, in English, Arabic or Spanish. Every version is checked again. |
| 7 | 7 | Phone width: the folded tactical card glows "42' goal build-up"; tap it and the move plays. | On a phone, a goal waits behind a glowing card instead of jumping in. |
| 8 | 13 | The README's "How well the Referee works" section. | I planted false claims into twenty fresh matches. The Referee caught 47 of 47. Only 44 percent of first drafts got through untouched, and that's exactly the point. |
| 9 | 10 | Run a fresh match: at a key moment the minute turns amber with "1x · desk checking", then the checked line lands with its stamp. | In a live match, the match slows to real time at each key moment until the checked line lands. |
| 10 | 9 | Foundry's Tracing page with one moment's workflow run open. | It runs on Azure Container Apps with managed identity, traced in Foundry, and deployed with Bicep and GitHub Actions. |
| 11 | 5 | The Jahbadh logo and the live link. | Jahbadh. AI that explains the game, and proves every word. |

Total: 114 seconds.

**After recording:** check the clip is under 2:00, upload it, and add its link to `docs/submission.md` and the README's top lines.
