// The live slow-down, read from the stream: the server sets the pace, the page only follows it.

import type { DeskStep, Moment, StepUpdate } from "../api/types";
import type { DeskState } from "./desk";

/** The match is running slower than its speed because the desk is checking a key moment. */
export function isSlowed(desk: DeskState): boolean {
  return !desk.ended && desk.info !== null && desk.pace !== null && desk.pace.speed < desk.info.speed;
}

/** The earliest key moment still holding the match, if the page knows it. */
export function holdingMoment(desk: DeskState): Moment | null {
  for (const id of desk.pace?.holding ?? []) {
    const moment = desk.thinking.find((m) => m.id === id);
    if (moment) return moment;
  }
  return null;
}

/** The speed the match clock runs at between messages. */
export function clockSpeed(desk: DeskState): number {
  return desk.pace?.speed ?? desk.info?.speed ?? 6;
}

/** The match second a moment's checked line was published, from its publish step. */
export function landedAt(desk: DeskState, momentId: string): number | null {
  return desk.steps[momentId]?.find((s) => s.step === "publish")?.t ?? null;
}

/** The chips for a moment's steps: the base chain, a rewrite and second check only when one happened, then
 *  publish. Only finished steps are lit; nobody knows in advance which step comes next. */
export function stepChips(steps: StepUpdate[]): { step: DeskStep; done: boolean }[] {
  const done = new Set(steps.map((s) => s.step));
  const rewrote = done.has("rewrite") || done.has("recheck");
  const order: DeskStep[] = ["analyst", "tactical", "writer", "referee",
    ...(rewrote ? (["rewrite", "recheck"] as DeskStep[]) : []), "publish"];
  return order.map((step) => ({ step, done: done.has(step) }));
}
