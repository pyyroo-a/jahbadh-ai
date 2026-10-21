// The words the desk shows for its switches and checks.

import type { DeskStep, Language, MatchInfo, Persona, Rejection } from "../api/types";

export const PERSONAS: { key: Persona; label: string }[] = [
  { key: "pundit", label: "Studio pundit" }, { key: "casual", label: "Casual fan" }, { key: "fantasy", label: "Fantasy" },
];

export const LANGUAGES: { key: Language; label: string }[] = [
  { key: "en", label: "EN" }, { key: "ar", label: "AR" }, { key: "es", label: "ES" },
];

export const LAYER_LABELS: Record<Rejection["layer"], string> = {
  deterministic: "Number and ID check",
  semantic: "Referee judge",
  persona: "Persona re-check",
  localization: "Translation check",
};

export const COMBO_NOTICES = {
  limit: "This live match can't take another version just now.",
  finished: "This live match has ended, so there's nothing new to add.",
  failed: "That version couldn't be added just now. Please try again.",
};

export const GOAL_LABELS = {
  row: "Goal build-ups",
  title: (minute: number) => `How the ${minute}' goal was built`,
  fromData: "The move, from the match data",
  noBuildUp: "No passes or carries before the shot in this move.",
  cardHint: (minute: number) => `${minute}' goal build-up`,
};

export const NOTES: Record<string, string> = {
  "persona fallback": "Shown in the pundit's words",
  "english fallback": "Shown in English",
  "raw translation": "Machine translation",
};

export const TACTICAL_CARD = { title: "Tactical view", hint: "Shapes, heatmaps and evidence. Tap to open." };

export const FEED_LABELS = {
  happening: "What's happening",
  more: (n: number) => `Show ${n} more ${n === 1 ? "event" : "events"}`,
};

/** Shown in live and ingest mode, where the desk's lines take about a minute of real time to write and check.
 *  Live slows to real time for that minute; an outside feed sets its own pace, so it gets no number. */
export function speedNote(info: MatchInfo): string | null {
  if (info.mode === "live") {
    return "Quick lines arrive straight away. At each key moment the match slows to real time while the desk writes " +
      "and checks its line, so it lands within about a minute of the moment.";
  }
  if (info.mode === "ingest") {
    return "Quick lines arrive straight away. The desk's checked lines land a minute or two after each moment.";
  }
  return null;
}

/** Live: the match slows to real time while the desk writes and checks a key moment's line. */
export const SLOWDOWN = {
  pill: "1x · desk checking",
  banner: "Desk review",
  bannerSub: "Slowed so the desk can write and check its line",
  checking: (label: string) => `The desk is checking ${label}.`,
  checkingSub: "The match is slowed to real time so its agents can write and check the line before play moves on.",
  controlNote: "At each key moment the match slows to real time while the desk checks its line.",
  landed: (t: number) => `Checked, landed at ${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`,
};

export const STEP_LABELS: Record<DeskStep, string> = {
  analyst: "Analyst", tactical: "Tactical", writer: "Writer", referee: "Referee", rewrite: "Rewrite",
  recheck: "Referee again", publish: "Publish",
};

export const WATCH_LABELS = {
  table: "Player watch · sort by any column · click a player to follow",
  feed: "Desk lines about your players first",
};

export const INGEST_LABELS = {
  button: "Watch an outside feed",
  badge: "Ingest · events from an outside feed",
  note: "These events come from our demo feeder, sent through the same ingest API an outside system would use.",
};
