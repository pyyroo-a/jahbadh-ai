// What a cited metric or a set of events draws on the pitch. Every number comes from the metric itself;
// these only move it onto the broadcast pitch. A metric with nothing to draw gives { kind: "none" }.

import type { EventLine, MatchInfo, Metric } from "../api/types";
import { LENGTH, WIDTH, type Rect, attackingRect, fromAttacking, toSvg, zoneRect } from "./coords";

export type Dot = { x: number; y: number; label: string; team: string };
export type Layer =
  | { kind: "heat"; cells: { x: number; y: number; w: number; h: number; v: number }[]; team: string }
  | { kind: "dots"; dots: Dot[] }
  | { kind: "network"; nodes: Dot[]; edges: { x1: number; y1: number; x2: number; y2: number; count: number; team: string }[] }
  | { kind: "shots"; shots: { x: number; y: number; xg: number; goal: boolean; team: string }[] }
  | { kind: "zone"; rect: Rect; label: string }
  | { kind: "none" };

const NONE: Layer = { kind: "none" };

/** The team a subject belongs to (a team id, or a player in either squad), or null for "MATCH" and strangers. */
function teamFor(subject: string, info: MatchInfo): { id: string; isHome: boolean } | null {
  if (subject === info.home.id) return { id: subject, isHome: true };
  if (subject === info.away.id) return { id: subject, isHome: false };
  if (info.home.players.some((p) => p.id === subject)) return { id: info.home.id, isHome: true };
  if (info.away.players.some((p) => p.id === subject)) return { id: info.away.id, isHome: false };
  return null;
}

function shirt(info: MatchInfo, playerId: string): string {
  const p = [...info.home.players, ...info.away.players].find((x) => x.id === playerId);
  return p ? String(p.shirt) : playerId;
}

function place(x: number, y: number, isHome: boolean): [number, number] {
  return toSvg(...fromAttacking(x, y, isHome));
}

export function metricLayer(m: Metric, info: MatchInfo): Layer {
  const team = teamFor(m.subject, info);
  if (!team) return NONE;
  const d = m.data as Record<string, unknown>;
  switch (m.name) {
    case "heatmap": {
      const grid = d.grid as number[][] | undefined;
      if (m.value === null || !grid?.length) return NONE;
      const [nx, ny] = (d.cells as [number, number]) ?? [grid.length, grid[0].length];
      const cw = LENGTH / nx, ch = WIDTH / ny;
      const cells = grid.flatMap((col, i) => col.flatMap((v, j) => v > 0
        ? [{ ...attackingRect(i * cw, j * ch, (i + 1) * cw, (j + 1) * ch, team.isHome), v }] : []));
      return cells.length ? { kind: "heat", cells, team: team.id } : NONE;
    }
    case "average_positions": {
      const players = (d.players ?? {}) as Record<string, [number, number]>;
      const dots = Object.entries(players).map(([id, [x, y]]) => {
        const [sx, sy] = place(x, y, team.isHome);
        return { x: sx, y: sy, label: shirt(info, id), team: team.id };
      });
      return dots.length ? { kind: "dots", dots } : NONE;
    }
    case "pass_network": {
      const raw = (d.nodes ?? {}) as Record<string, { pos: [number, number] | null }>;
      const placed = new Map<string, Dot>();
      for (const [id, n] of Object.entries(raw)) {
        if (!n.pos) continue;                         // hand-built data can have a receiver with no location
        const [x, y] = place(n.pos[0], n.pos[1], team.isHome);
        placed.set(id, { x, y, label: shirt(info, id), team: team.id });
      }
      const edges = ((d.edges ?? []) as [string, string, number][]).flatMap(([a, b, count]) => {
        const from = placed.get(a), to = placed.get(b);
        return from && to ? [{ x1: from.x, y1: from.y, x2: to.x, y2: to.y, count, team: team.id }] : [];
      });
      return placed.size ? { kind: "network", nodes: [...placed.values()], edges } : NONE;
    }
    case "shot_map": {
      const raw = (d.shots ?? {}) as Record<string, { x: number; y: number; xg: number; goal: boolean }>;
      const shots = Object.values(raw).map((s) => {
        const [x, y] = place(s.x, s.y, team.isHome);
        return { x, y, xg: s.xg, goal: s.goal, team: team.id };
      });
      return shots.length ? { kind: "shots", shots } : NONE;
    }
    case "zone_overloads":
      return typeof d.zone === "string"
        ? { kind: "zone", rect: zoneRect(d.zone, team.isHome), label: String(d.typical ?? "") } : NONE;
    default:
      return NONE;
  }
}

export type Arrow = { id: number; x1: number; y1: number; x2: number; y2: number };
export type Point = { id: number; x: number; y: number; type: EventLine["type"] };

export type ReplayStep = {
  id: number; kind: "pass" | "carry" | "shot" | "point"; x1: number; y1: number; x2: number; y2: number;
  shirt: string | null; team: string;
};

/** A goal's build-up in raw coordinates, in order: passes and carries as arrows, the shot as an arrow to where it
 *  was recorded ending, the rest (a won tackle, a free kick, a goal with no shot) as points. A scoring-team player's
 *  shirt number marks their first touch in a row. */
export function replaySteps(steps: EventLine[], info: MatchInfo): ReplayStep[] {
  const team = steps.at(-1)?.team_id ?? "";
  let last: string | null = null;
  return steps.map((e) => {
    const [x1, y1] = toSvg(e.x, e.y);
    const arrow = e.end_x !== null && e.end_y !== null && (e.type === "PASS" || e.type === "CARRY" || e.type === "SHOT");
    const [x2, y2] = arrow ? toSvg(e.end_x!, e.end_y!) : [x1, y1];
    const kind = !arrow ? "point" : e.type === "PASS" ? "pass" : e.type === "CARRY" ? "carry" : "shot";
    let mark: string | null = null;
    if (e.team_id === team && e.player_id && e.player_id !== last) {
      mark = shirt(info, e.player_id);
      last = e.player_id;
    }
    return { id: e.id, kind, x1, y1, x2, y2, shirt: mark, team: e.team_id };
  });
}

/** A claim's events in raw coordinates: passes and carries with an end point as arrows, the rest as points. */
export function eventLayer(events: EventLine[]): { arrows: Arrow[]; points: Point[] } {
  const arrows: Arrow[] = [], points: Point[] = [];
  for (const e of events) {
    const [x1, y1] = toSvg(e.x, e.y);
    if ((e.type === "PASS" || e.type === "CARRY") && e.end_x !== null && e.end_y !== null) {
      const [x2, y2] = toSvg(e.end_x, e.end_y);
      arrows.push({ id: e.id, x1, y1, x2, y2 });
    } else {
      points.push({ id: e.id, x: x1, y: y1, type: e.type });
    }
  }
  return { arrows, points };
}
