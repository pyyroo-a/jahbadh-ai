// Goal replays: which goal's build-up plays, when, and how fast. The server picks each move's steps; these only
// decide when to draw them.

import type { EventLine, FeedItem, MatchInfo } from "../api/types";

export const GOAL_FRESH_S = 60;        // match seconds a goal can still play by itself (a skip's old goals can't)
export const HOLD_MS = 4000;           // how long the finished move stays before the pitch goes back

export type GoalChip = { goalId: number; minute: number; teamId: string; label: string };

/** One chip per goal so far, in match order: the minute and the scorer's last name ("42' Quill"). */
export function goalChips(events: EventLine[], info: MatchInfo): GoalChip[] {
  const players = [...info.home.players, ...info.away.players];
  return events.filter((e) => e.type === "GOAL").map((e) => {
    const name = players.find((p) => p.id === e.player_id)?.name.split(" ").pop();
    return { goalId: e.id, minute: e.minute, teamId: e.team_id, label: `${e.minute}' ${name ?? e.team_id}` };
  });
}

/** The newest goal no more than GOAL_FRESH_S behind the clock. */
export function freshGoal(events: EventLine[], clock: number): EventLine | null {
  const goal = events.findLast((e) => e.type === "GOAL");
  return goal && clock - goal.t <= GOAL_FRESH_S ? goal : null;
}

/** A goal moment's own goal line. Every other moment, and a goal not yet streamed, has none. */
export function goalOfItem(item: FeedItem, eventsById: Record<number, EventLine>): EventLine | null {
  if (item.moment.kind !== "goal") return null;
  return item.moment.event_ids.map((id) => eventsById[id]).find((e) => e?.type === "GOAL") ?? null;
}

/** Milliseconds per step: 0.8 s for short moves, quicker for long ones so a replay stays around 5 to 7 s. */
export function stepMs(steps: number): number {
  return Math.round(Math.min(800, Math.max(350, 6000 / Math.max(1, steps))));
}

/** The newest goal, while it hasn't been watched. An older unwatched goal never glows. */
export function newestUnwatched(chips: GoalChip[], watched: ReadonlySet<number>): GoalChip | null {
  const newest = chips.at(-1);
  return newest && !watched.has(newest.goalId) ? newest : null;
}

export type ReplayInputs = {
  request: number | null;        // a goal the viewer asked for (a chip, or opening the phone card)
  lineGoal: number | null;       // the goal of a selected desk line about a goal
  lineDone: boolean;             // that line's replay has already played
  fresh: number | null;          // the newest goal, while it is fresh
  latched: number | null;        // a goal that started by itself: it plays to the end even once it isn't fresh
  watched: ReadonlySet<number>;
  overview: boolean;             // nothing selected
  phone: boolean;
};

/** Which goal plays now: a request, then a selected goal line, then (on a wide screen's overview) a fresh goal,
 *  then the goal that already started by itself. The fresh goal is always the newest, so it takes over. */
export function pickReplay(i: ReplayInputs): number | null {
  if (i.request !== null) return i.request;
  if (i.lineGoal !== null) return i.lineDone ? null : i.lineGoal;
  if (!i.overview || i.phone) return null;
  if (i.fresh !== null && !i.watched.has(i.fresh)) return i.fresh;
  if (i.latched !== null && !i.watched.has(i.latched)) return i.latched;
  return null;
}

export const LATCH_MS = 250;     // a goal fresh this long (real time) has really just happened, not passed in a skip
