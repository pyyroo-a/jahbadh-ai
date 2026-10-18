// One reducer over the stream messages. Everything the desk draws comes from here; the browser never
// computes a football number itself.

import type {
  EventLine, FeedItem, Language, MatchInfo, MatchState, Moment, MomentFailure, Persona, Rejection, RenderedClaim,
  StreamEnd, StreamMessage,
} from "../api/types";

export type DeskState = {
  info: MatchInfo | null;
  events: EventLine[];
  eventsById: Record<number, EventLine>;
  state: MatchState | null;
  states: MatchState[];              // one a minute, for single-metric mode
  thinking: Moment[];
  items: FeedItem[];
  failures: MomentFailure[];
  ended: StreamEnd | null;
  lastId: number;
};

export const initialDesk: DeskState = {
  info: null, events: [], eventsById: {}, state: null, states: [], thinking: [], items: [], failures: [], ended: null, lastId: -1,
};

const renderKey = (r: RenderedClaim) => `${r.claim_id}|${r.persona}|${r.language}`;
const rejectionKey = (r: Rejection) => `${r.claim_id}|${r.layer}|${r.attempt}|${r.persona}|${r.language}|${r.text}`;

function mergeBy<T>(have: T[], add: T[], key: (x: T) => string): T[] {
  const seen = new Set(have.map(key));
  return [...have, ...add.filter((x) => !seen.has(key(x)) && seen.add(key(x)))];
}

export function reduce(s: DeskState, m: StreamMessage): DeskState {
  if (m.kind === "match") return { ...initialDesk, info: m.data, lastId: m.id };
  if (m.id <= s.lastId) return s;           // a reconnect resent something we already have
  const next = { ...s, lastId: m.id };
  switch (m.kind) {
    case "event":
      return { ...next, events: [...s.events, m.data], eventsById: { ...s.eventsById, [m.data.id]: m.data } };
    case "state":
      return { ...next, state: m.data, states: [...s.states, m.data] };
    case "thinking":
      return { ...next, thinking: [...s.thinking.filter((t) => t.id !== m.data.id), m.data] };
    case "feed": {
      const others = s.items.filter((i) => i.moment.id !== m.data.moment.id);
      const items = [...others, m.data].sort((a, b) => a.moment.t - b.moment.t);
      return { ...next, items, thinking: s.thinking.filter((t) => t.id !== m.data.moment.id) };
    }
    case "failure":
      return { ...next, failures: [...s.failures, m.data], thinking: s.thinking.filter((t) => t.id !== m.data.moment_id) };
    case "renders": {
      const { moment_id, renders, rejections } = m.data;
      const items = s.items.map((i) => i.moment.id !== moment_id ? i : {
        ...i, renders: mergeBy(i.renders, renders, renderKey), rejections: mergeBy(i.rejections, rejections, rejectionKey),
      });
      return { ...next, items };
    }
    case "end":
      return { ...next, ended: m.data, thinking: [] };
    case "cue":
      return next;                           // the overlay preview reads cues on its own (Task 12a)
  }
}

/** Every claim of the item has a render in this persona and language (mirrors agents.combos.has_combo). */
export function hasCombo(item: FeedItem, persona: Persona, language: Language): boolean {
  return item.claims.every((c) =>
    item.renders.some((r) => r.claim_id === c.id && r.persona === persona && r.language === language));
}

export type ShownText ={ text: string; note: string | null; dir: "rtl" | "ltr" };

/** The words for one claim in a persona and language: that combo, else the persona's English, else the claim. */
export function claimText(item: FeedItem, claimId: string, persona: Persona, language: Language): ShownText {
  const find = (lang: Language) =>
    item.renders.find((r) => r.claim_id === claimId && r.persona === persona && r.language === lang);
  const render = find(language) ?? find("en");
  if (render) {
    const arabic = render.language === "ar" && render.note !== "english fallback";
    return { text: render.text, note: render.note, dir: arabic ? "rtl" : "ltr" };
  }
  const claim = item.claims.find((c) => c.id === claimId);
  return { text: claim?.text ?? "", note: null, dir: "ltr" };
}

/** The writer's drafts the Referee turned down, plus this combo's own persona and translation rejections. */
export function rejectionsFor(item: FeedItem, persona: Persona, language: Language): Rejection[] {
  return item.rejections.filter((r) => r.persona === null
    || (r.persona === persona && (r.language === null || r.language === language)));
}

export function nextMomentTime(info: MatchInfo, clock: number): number | null {
  const later = info.moment_times.filter((t) => t > clock);
  return later.length ? Math.min(...later) : null;
}
