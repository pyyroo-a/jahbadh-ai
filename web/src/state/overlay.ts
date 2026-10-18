// What a broadcast graphics system would have on screen at a given second: the cues on air, newest first.

import type { OverlayCue } from "../api/types";

export const MAX_ON_SCREEN = 2;

export function activeCues(cues: OverlayCue[], clock: number): OverlayCue[] {
  return cues
    .filter((c) => c.match_time <= clock && clock < c.match_time + c.duration_s)
    .sort((a, b) => b.match_time - a.match_time)
    .slice(0, MAX_ON_SCREEN);
}

export const MATCH_END_S = 5400;
export const MAX_TICK_S = 60;       // a state arrives every match minute, so the clock never runs further ahead

/** The match clock between messages: it keeps running at the stream's speed, as a broadcast clock would. */
export function tickingClock(lastT: number, lastAt: number, now: number, speed: number, running = true): number {
  if (!running) return lastT;
  const ran = Math.min(MAX_TICK_S, (Math.max(0, now - lastAt) / 1000) * speed);
  return Math.min(MATCH_END_S, lastT + ran);
}
