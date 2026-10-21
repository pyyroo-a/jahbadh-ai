# Live slow-down: the match waits for the desk's checked line

Written 21 Oct 2026 with the user, after the first live run on Azure. Part of Plan 4 (`docs/superpowers/plans/2026-10-19-plan-4-ship.md`), between the delay note and Task 16.

## Why

In the first live run the desk's checked lines landed about 6 match minutes after the moment they describe. A goal at 55' got its line in the 61st minute. The user, watching as a fan and as a pundit, found that frustrating: it felt like delayed news, and reading it meant missing what was happening on the pitch right then.

The delay is real work, not a pricing tier. Each key moment runs the whole chain in order (Analyst, Tactical, Writer, Referee, a rewrite and second check when the Referee rejects a claim, then Persona, Localize and Publish). In the run on 20 Oct that was about 10 model calls per moment, about 56 real seconds, and at 6x that is about 6 match minutes. A model on its own can answer in a second or two; the time goes on checking every claim against the data, which is the thing that makes Jahbadh different. So the design is honest about it: the match slows down so the desk can write and check its line.

**Success:** in live mode, a key moment at 55' gets its checked line before 56', and 57' at the latest.

## Goals

- In live mode, when the clock reaches a key moment, the match drops from its speed (6x) to real time (1x) until that moment's checked line (or failure) is published, then goes back to 6x.
- Everyone can see the pace changed, and why.
- Each persona sees it in its own way (below).
- Each checked line in live and ingest mode shows when it landed, so anyone can see it beat the minute.
- The live speed note from the delay-note change is updated, because "about 6 match minutes" stops being true.

## Non-goals

- Making the chain itself faster. That is a separate, later piece of work (the user's stretch goal if time allows), and it would need its own eval re-run.
- Any change to replay. Replay's lines already land `REPLAY_DESK_LAG_S` (20 match seconds) after each moment.
- Slowing an outside feed (ingest). The server does not set that pace.
- Slowing for a spotlight the viewer asked for. They chose to wait for it.

## Anti-goals (a failure even if it works)

- **Slowing before the moment.** The server knows the whole simulated match up front. If the pace dropped even a second early, viewers would learn something is about to happen. The slow-down starts at the moment's own time, never before.
- **Changing what the desk says or what happened.** Every event still arrives at its true match time. Only the pace changes. No result is tuned to look faster.
- **A made-up progress bar.** Nobody knows in advance how long a moment takes. Progress shown is the desk's real finished steps, nothing estimated.
- **A frozen match.** A stuck moment (rate limit, hung call) can never hold the match at 1x for long.
- **Hiding it.** The slow-down is always labelled.

## How it behaves (decided with the user)

**Pace rules (live mode only):**
- A key moment holds the match at 1x from the second its `thinking` item goes out until its `feed` or `failure` item is published.
- While any key moment holds it, the pace is 1x. When none does, it is `LIVE_SPEED` (6x). Two moments close together keep it at 1x until both are in (user: "that's okay").
- A failed moment ends its hold just like a published one.
- Cap: a moment holds the match for at most about 2 real minutes (builder's constant, about 120 s). After that it stops holding, the pace goes back to 6x if nothing else holds it, and the moment keeps working and publishes when it can.
- Spotlights never hold the match.
- "Skip to next moment" works as today. Skipping does not cancel a hold that is still running.
- The extra versions a viewer adds (persona and language combos) never hold the match. Only the moment's own checked line does.
- **Moments go first (executor's call, 21 Oct).** Today a moment's desk work and every extra version share one queue of 3 (`LIVE_CONCURRENCY`), so after a moment publishes, up to 8 extra versions could sit ahead of the next key moment while the match waits at 1x, which would let extra versions hold the match after all. So a waiting key moment (and a spotlight) always takes the next free place before any waiting extra version. The limit of 3 at once stays, so the load on the 250k tokens-per-minute deployment does not grow.
- **Full time does not hold (executor's call, 21 Oct).** `full_time` is a key moment, but after the whistle there is nothing left to slow down, so its line comes the usual way: no amber minute, no pill, no banner. Its thinking card keeps the step chips.
- Idle cancel (nobody watching for 60 s) works as today.

**What everyone sees (all personas, desktop and phone, live mode):**
- While the match is slowed, the minute in the top bar turns amber and a pill beside it reads "1x · desk checking".
- Each checked line, in live and ingest mode, carries a stamp such as "55' goal · checked, landed at 55:56" (the moment's label and minute, and the match clock when its feed item was published). Not in replay, where the timing is staged.

**Per persona (the persona already picks the layout):**
- **Casual fan** (desktop three-column view, and the phone Fan layout): a broadcast-style banner, "DESK REVIEW · 55' GOAL", with "Slowed so the desk can write and check its line". On desktop it sits across the top of the pitch (the tactical view already has a slot for things drawn over the pitch). On phones the pitch is folded away, so the banner sits at the top of the stack, above the momentum bar. With two moments in flight it names the earliest one still holding.
- **Studio pundit and Fantasy** (Analyst and Player watch layouts, desktop and phone): the thinking card for a holding moment reads "The desk is checking the 55' goal. The match is slowed to real time so its agents can write and check the line before play moves on." Below it, the desk's real steps as chips, each lit as it finishes: Analyst, Tactical, Writer, Referee, then Rewrite and Referee again only if the Referee sent a claim back, then Publish. A moment that does not hold the match (a spotlight, or one past the cap) keeps its usual thinking card, with the step chips but without the slowed sentence.

**Speed note (live):** replaces the delay-note text: "Quick lines arrive straight away. At each key moment the match slows to real time while the desk writes and checks its line, so it lands within about a minute of the moment." Ingest keeps its note without a number. Replay shows none.

Mockups the user approved: `.superpowers/brainstorm/1044-1792569373/content/slowdown-by-persona.html` (local, gitignored). Names, score and the line in them are placeholders.

## What the server adds (the protocol)

Two new stream kinds, so the page never has to guess:

- **`pace`**: sent at the clock time the pace changes. Carries the speed now in force and the ids of the moments holding it (empty when back to normal). The page's ticking clock runs at the latest `pace` speed instead of `MatchInfo.speed`. `MatchInfo.speed` stays the base speed (6).
- **`step`**: sent when one of the desk's steps finishes for a moment: the moment id, the step name, and the match clock `t` when it finished. Sent for live and ingest moments, including spotlights. Replay sends none. The last step, Publish, goes out right before the moment's `feed` item at the same clock time, and its `t` is where the "landed at 55:56" stamp comes from (executor's call, 21 Oct): a `feed` message carries only the FeedItem, with no time of its own, and the page's own clock would be wrong after a reconnect replays the history in a burst. A failed moment gets no Publish step.

Both go through `StreamKind` (Python) and `STREAM_KINDS` / `StreamMessage` (web) like the existing kinds, keep the "never ahead of the clock" rule, and leave every existing kind unchanged. Overlay cues are unchanged.

## Constraints

- Plan 4's Global Constraints hold: no new runtime dependencies, TDD per step, whole suite green, no em or en dashes in code comments, UI copy, docs or commit text, friendly tone.
- Data-true (see anti-goals). The pace logic only ever reacts to moments that have already started.
- No extra model calls, so no extra cost. A live match gets longer: about 15 minutes at 6x today, an estimated 23 or so with 11 key moments at about 56 s each.
- The user commits every change; the executor gives commit instructions and waits for "committed". Shipping to Azure is the user's push plus GitHub Actions > Deploy.
- Seeing it in the browser for real needs a paid live run (about $0.35, more with extra versions), so it needs the user's yes. Until then the behaviour is proven by tests with fake desks and fake sleeps, as the live tests already do.

## Left to the builder

- How the pacing loop in `LiveRun._play` advances the clock when the pace changes in the middle of a gap between items (the current loop sleeps the whole gap at one speed; it has to wake and recompute when a hold starts or ends). Keep the existing skip and idle behaviour and the existing tests green.
- How the pipeline reports finished steps (for example an optional callback passed to `run_moment` that each `_Step` calls, or Agent Framework's own workflow events). The eval and the showcase CLI must work unchanged.
- The exact step names in the protocol, and how Persona and Localize map to the "Publish" chip.
- The exact cap value (about 120 s) and its constant name.
- Component structure, CSS, and where the amber pill lives in `TopBar`.
- The exact wording of the stamp and the banner's second line, within the meaning above (no dashes).
