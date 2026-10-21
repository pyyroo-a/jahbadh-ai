# Goal arrows: a TV-style replay of each goal's build-up

Written 21 Oct 2026 with the user. Part of Plan 4 (`docs/superpowers/plans/2026-10-19-plan-4-ship.md`), after Task 16 and before Task 17, so the README screenshots and the video can show it. Mockups: `.superpowers/brainstorm/2151-1792605320/content/` (`goal-arrows-look.html`, option A chosen; `goal-arrows-again.html`).

## Why

A goal on the tactical view today is a dot. The user wants judges to see the move that made it: every pass and run in order, then the shot. In the user's words, "the build up is what we need to show the realism". It should feel like a broadcast replay graphic, with the arrows coming one after the other.

**Success:** a judge watching the replay sees Quill's 42' goal draw itself on the pitch, pass by pass (ten steps with a free kick), then can watch it again from a chip under the pitch.

(The mockups used a 68' Quill goal from plain seed 42. The showcase match runs seed 42 with the demo storyline, which changes the second half; its goals are 15', 22', 27', 42', 47', 78', 79' and 83', measured 21 Oct. Copy examples like "68' Quill" below are only illustrations.)

## Goals

- When a goal lands and nothing is selected, the tactical view plays that goal's build-up once as a TV-style replay, holds it, then goes back to the usual view.
- A "Goal build-ups" row under the pitch keeps one chip per goal so far; tapping a chip plays that goal's replay again.
- Selecting one of the desk's lines about a goal shows that line's evidence as today, with the build-up replay drawn alongside it and clearly labelled as coming from the match data.
- It works the same in replay, live and an outside feed (ingest), in all three layouts (Fan, Analyst, Player watch) and on phones.

## Non-goals

- Any change to the simulator, the desk, the agents or what they cite. The showcase output is not re-run (no model calls, no cost).
- Arrows for anything except goals (big chances, other moves).
- Animating players or the ball between events. Only the recorded events are drawn.

## Anti-goals (a failure even if it works)

- **Made-up detail.** Every shot in the data ends at the goal centre (105, 34) for the home team and (0, 34) for the away team, so the shot arrow ends exactly there and nothing shows where in the goal it went. No smoothing, no invented curve, no extra touches.
- **Passing the build-up off as the agents' evidence.** The agents never cited these passes. When the replay sits next to a claim's evidence, it is labelled as the move from the match data.
- **Interrupting the reader.** If the viewer is reading another line's evidence when a goal lands, nothing takes the pitch away from them.
- **The browser deciding the move.** The server picks which events make the build-up; the browser only draws what it is sent.

## How it behaves (decided with the user)

**The look (option A, "TV-style replay").** The arrows draw one after another in match order. Passes are solid arrows and carries are dashed arrows, in the scoring team's colour. The scorer's and each passer's shirt number sits in a small dot at the start of their action. The shot is a gold (amber) arrow from where it was taken to the goal centre. A numbered step list under the pitch lights up in time with the arrows. The title reads "How the 68' goal was built".

**When it plays (the user's "mix").**
- Nothing selected (the overview): a new goal plays its replay by itself, once. It holds for a few seconds after the last arrow, then the pitch goes back to the usual formations.
- Reading another line's evidence: the evidence stays. The new goal's chip in the row glows until it has been watched.
- Tapping a chip: plays that goal's replay (again).
- Tapping one of the desk's lines about a goal: the usual "Evidence for the 68' claim" view, with the replay played on the same pitch and a label "The move, from the match data".

**The "Goal build-ups" row.** Under the pitch, one chip per goal so far, in the scoring team's colour, reading the minute and the scorer's surname ("68' Quill"). The newest unwatched chip glows. This row is the only "watch again" control. It wraps on phones.

**Phones (the user's choice).** The tactical view stays folded in its card when a goal lands; it never pops open by itself. While a goal is unwatched, the card's header shows a glowing hint, for example "68' goal build-up", and the replay plays when the viewer opens the card. The chip row lives inside the card, under the pitch, as on desktop.

## The data (measured on seeds 42, 7 and 123)

A build-up runs from when the scoring team last won the ball to the shot. Walking back from the goal's shot through the match events:

- **Kept as steps:** the scoring team's completed passes and carries.
- **Starts the move (kept as the first step):** the scoring team's own successful tackle or interception.
- **Kept as a marker, the move carries on:** a foul by the other team (a free kick).
- **Ends the walk (not kept):** any pass, carry or shot by the other team; the other team's successful tackle or interception; the scoring team's own failed pass or failed carry, earlier shot or foul; a kick-off, half time or an earlier goal.
- **Skipped:** pressures, failed tackles and interceptions, cards, substitutions, formation and press changes.

What that gives in real data: from nothing but the shot (a loose ball shot straight away, seed 42 at 47') up to 20 actions over 80 seconds (seed 123 at 76'). Most goals are scored from 0.1 to 6 m, so the shot arrow is often short; a dot at the shot spot keeps it visible. Some event positions are on the pitch edge (x = 0 or 105) because the data clamps them there; they are drawn as they are.

## How it is built (decided with the user)

- **Server.** The goal's event line carries its build-up: an ordered list of steps, each with the event id, type, team, player and related player, start and end positions, and the event's lines in English, Arabic and Spanish (the existing template lines). The shot is the last step. The walk runs on the events before the goal, so live and ingest (which only know the past) get the same result as replay. Other event lines are unchanged.
- **Browser.** Draws only the steps it is sent, in their order, using the existing pitch frame (raw events are already in the broadcast frame). The step list shows each step's line in the chosen language.

## Settled after the builder check (my calls, flagged for the user's review)

- **One step per event.** Each pass, carry, tackle, interception or foul is its own step, and its text is the event's existing template line in the chosen language ("Quill finds Lindqvist", "Lindqvist carries the ball forward"). The mockup's merged "Carry #20 (two runs)" and "Cross #72 to #40" were only illustrations: the data has no "cross" and merging would be a made-up summary.
- **Which desk lines count as "about a goal".** Only the claims in a `goal` moment (`moment.kind == "goal"`); their replay is that moment's own goal. Recaps, check-ins, spotlights and full time cite goals too, but often several, so they show their evidence as today with no replay.
- **A chip tapped while another line's evidence is open.** The replay plays on the same pitch over that evidence and, after its hold, the pitch goes back to the evidence the viewer was reading. The selection is not cleared. The same is true on the overview: the replay is a layer over whatever was showing, and it always returns there.
- **Goals from an outside feed that don't look like the simulator's.** The server walks back from the goal's shot (`detail.shot_id`), or from the goal itself when there is none. The shot arrow uses the end point the feed recorded, never a forced goal centre (data-true either way: the simulator's shots end at the goal centre). A goal with no shot and no passes before it still gets a chip; its replay is a single point at the goal's position.

## Left to the builder (my calls, flagged for the user's review)

- **Pace.** About 0.8 s per step for short moves, faster for long ones so a whole replay stays around 5 to 8 seconds (for example 6 s divided by the steps, kept between 0.35 s and 0.8 s). Hold about 4 s after the last arrow before fading back.
- **A move with no steps before the shot.** The step list says so plainly, for example "No passes or carries before the shot in this move."
- **Several goals arriving at once** (a replay skip or a fast catch-up): only the newest one plays by itself; the rest get chips.
- **Where the free-kick marker goes:** at the foul's position, as a small point in the step list order ("Foul by Lindqvist on Jansen").
- **Field name and shape** on the event line, test names, CSS class names.
- **Reduced motion:** if the viewer's system asks for reduced motion, draw the whole move at once instead of animating it.
