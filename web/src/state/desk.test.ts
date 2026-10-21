import { describe, expect, it } from "vitest";
import type {
  EventLine, FeedItem, MatchInfo, Moment, Rejection, RenderedClaim, StreamMessage, Team,
} from "../api/types";
import { claimText, comboWaiting, hasCombo, initialDesk, nextMomentTime, reduce, rejectionsFor, replaySkip } from "./desk";

const team = (id: string, name: string): Team => ({
  id, name, formation: "4-3-3", players: [],
  tactics: { press_height: 0.5, width: 0.5, tempo: 0.5, directness: 0.5 },
});
const info: MatchInfo = {
  match_id: "match-042", mode: "replay", home: team("NBR", "Northbridge FC"), away: team("RMU", "Rivermouth United"),
  speed: 6, precomputed: true, model: "gpt-5-mini", created: "2026-10-18", moment_times: [25, 295, 885],
};
const msg = (id: number, kind: StreamMessage["kind"], data: unknown): StreamMessage =>
  ({ id, kind, data }) as StreamMessage;
const ev = (id: number, t = id): EventLine => ({
  id, t, minute: Math.floor(t / 60) + 1, type: "PASS", team_id: "NBR", player_id: "NBR-9", related_player_id: null,
  x: 50, y: 30, end_x: 60, end_y: 30, outcome: true, xg: null, speed_kmh: null, lines: { en: "pass", ar: "تمريرة", es: "pase" },
});
const moment = (id: string, t = 885): Moment =>
  ({ id, kind: "goal", t, team_id: "NBR", player_id: null, event_ids: [], label: `${id} label` });
const item = (id: string, t = 885, extra: Partial<FeedItem> = {}): FeedItem => ({
  moment: moment(id, t), metrics: [], stats: {}, latency_s: 1, renders: [], rejections: [],
  claims: [{ id: "c1", text: "the claim's own text", metric_ids: [], event_ids: [], figures: [] }], ...extra,
});
const r = (persona: RenderedClaim["persona"], language: RenderedClaim["language"], text: string,
  note: string | null = null): RenderedClaim => ({ claim_id: "c1", persona, language, text, note });
const itemWith = (renders: RenderedClaim[]) => item("goal-885", 885, { renders });
const withMatch = () => reduce(initialDesk, msg(0, "match", info));

describe("reduce", () => {
  it("ignores messages it has already seen", () => {
    let s = reduce(initialDesk, msg(0, "match", info));
    s = reduce(s, msg(1, "event", ev(2)));
    s = reduce(s, msg(1, "event", ev(2)));
    expect(s.events).toHaveLength(1);
    expect(s.eventsById[2].lines.en).toBe("pass");
    expect(s.lastId).toBe(1);
  });

  it("starts over on a new match message", () => {
    let s = reduce(withMatch(), msg(1, "event", ev(2)));
    s = reduce(s, msg(0, "match", { ...info, match_id: "live-7" }));
    expect(s.events).toEqual([]);
    expect(s.info?.match_id).toBe("live-7");
    expect(s.lastId).toBe(0);
  });

  it("swaps thinking for the published item", () => {
    let s = reduce(withMatch(), msg(5, "thinking", moment("goal-885")));
    expect(s.thinking.map((m) => m.id)).toEqual(["goal-885"]);
    s = reduce(s, msg(6, "feed", item("goal-885")));
    expect(s.thinking).toEqual([]);
    expect(s.items.map((i) => i.moment.id)).toEqual(["goal-885"]);
  });

  it("keeps items in match order and clears thinking on failure", () => {
    let s = reduce(withMatch(), msg(1, "thinking", moment("card-25", 25)));
    s = reduce(s, msg(2, "thinking", moment("goal-885")));
    s = reduce(s, msg(3, "feed", item("goal-885")));
    s = reduce(s, msg(4, "failure", { moment_id: "card-25", error: "RuntimeError: 429" }));
    s = reduce(s, msg(5, "feed", item("card-295", 295)));
    expect(s.items.map((i) => i.moment.id)).toEqual(["card-295", "goal-885"]);
    expect(s.failures.map((f) => f.moment_id)).toEqual(["card-25"]);
    expect(s.thinking).toEqual([]);
  });

  it("takes the latest state and ends by clearing thinking", () => {
    let s = reduce(withMatch(), msg(1, "state", { t: 60, minute: 2 }));
    s = reduce(s, msg(2, "thinking", moment("full_time-5400", 5400)));
    s = reduce(s, msg(3, "end", { reason: "cancelled" }));
    expect(s.state?.minute).toBe(2);
    expect(s.states.map((x) => x.t)).toEqual([60]);              // every minute is kept for the metric line
    expect(s.thinking).toEqual([]);
    expect(s.ended).toEqual({ reason: "cancelled" });
  });

  it("merges late renders once", () => {
    let s = reduce(withMatch(), msg(1, "feed", item("goal-885")));
    const update = { moment_id: "goal-885", renders: [r("casual", "es", "texto")], rejections: [] };
    s = reduce(s, msg(2, "renders", update));
    s = reduce(s, msg(3, "renders", update));
    expect(s.items[0].renders).toEqual([r("casual", "es", "texto")]);
  });

  it("keeps cues for the overlay preview, once each", () => {
    let s = reduce(withMatch(), msg(1, "cue", { id: "event-21" }));
    s = reduce(s, msg(1, "cue", { id: "event-21" }));
    expect(s.lastId).toBe(1);
    expect(s.items).toEqual([]);
    expect(s.cues.map((c) => c.id)).toEqual(["event-21"]);
  });
});

describe("clock", () => {
  it("follows every timed message, not just events", () => {
    let s = reduce(withMatch(), msg(1, "event", ev(2, 20)));
    expect(s.clock).toBe(20);
    s = reduce(s, msg(2, "cue", { id: "claim-1", match_time: 45 }));
    expect(s.clock).toBe(45);
    s = reduce(s, msg(3, "thinking", moment("goal-885", 50)));
    s = reduce(s, msg(4, "state", { t: 60, minute: 2 }));
    expect(s.clock).toBe(60);
    s = reduce(s, msg(5, "event", ev(3, 58)));                // a late event never winds the clock back
    expect(s.clock).toBe(60);
  });
});

describe("what to show", () => {
  it("claimText falls back and picks the direction", () => {
    expect(claimText(itemWith([r("pundit", "ar", "نص")]), "c1", "pundit", "ar")).toEqual({ text: "نص", note: null, dir: "rtl" });
    expect(claimText(itemWith([r("pundit", "ar", "English", "english fallback")]), "c1", "pundit", "ar").dir).toBe("ltr");
    expect(claimText(itemWith([r("casual", "en", "Casual words")]), "c1", "casual", "es"))
      .toEqual({ text: "Casual words", note: null, dir: "ltr" });
    expect(claimText(itemWith([]), "c1", "casual", "es").text).toBe("the claim's own text");
    expect(claimText(itemWith([r("fantasy", "en", "Plain", "persona fallback")]), "c1", "fantasy", "en").note)
      .toBe("persona fallback");
  });

  it("lists the shared rejections plus this combo's own", () => {
    const rej = (layer: Rejection["layer"], persona: Rejection["persona"], language: Rejection["language"]): Rejection =>
      ({ claim_id: "c1", text: layer, layer, reasons: [], attempt: 1, persona, language });
    const all = [rej("deterministic", null, null), rej("semantic", null, null), rej("persona", "casual", null),
      rej("persona", "fantasy", null), rej("localization", "casual", "ar"), rej("localization", "casual", "es")];
    const got = rejectionsFor(item("goal-885", 885, { rejections: all }), "casual", "ar");
    expect(got).toEqual([all[0], all[1], all[2], all[4]]);
  });

  it("finds the next moment after the clock", () => {
    expect(nextMomentTime({ ...info, moment_times: [25, 295, 885] }, 300)).toBe(885);
    expect(nextMomentTime({ ...info, moment_times: [25, 295, 885] }, 295)).toBe(885);
    expect(nextMomentTime({ ...info, moment_times: [25] }, 300)).toBeNull();
  });
});

describe("hasCombo", () => {
  it("is ready only when every claim has that persona and language", () => {
    const two = item("goal-885", 885, {
      claims: [{ id: "c1", text: "a", metric_ids: [], event_ids: [], figures: [] },
        { id: "c2", text: "b", metric_ids: [], event_ids: [], figures: [] }],
      renders: [r("casual", "es", "uno"), { ...r("casual", "es", "dos"), claim_id: "c2" }, r("casual", "ar", "واحد")],
    });
    expect(hasCombo(two, "casual", "es")).toBe(true);
    expect(hasCombo(two, "casual", "ar")).toBe(false);
    expect(hasCombo(item("empty", 1, { claims: [] }), "fantasy", "ar")).toBe(true);
  });
});

describe("replaySkip", () => {
  it("lands just before the next moment, and the next skip moves on even if the clock lags", () => {
    const at = { ...info, moment_times: [25, 295, 885] };
    expect(replaySkip(at, 0, 0)).toEqual({ fromT: 20, seen: 25 });
    expect(replaySkip(at, 18, 25)).toEqual({ fromT: 290, seen: 295 });     // clock 18 is behind the 20 we asked for
    expect(replaySkip(at, 300, 295)).toEqual({ fromT: 880, seen: 885 });
    expect(replaySkip(at, 880, 885)).toBeNull();
    expect(replaySkip({ ...info, moment_times: [3] }, 0, 0)).toEqual({ fromT: 0, seen: 3 });
  });
});

describe("comboWaiting", () => {
  it("waits for a requested combo only while the match is still going", () => {
    const one = item("goal-885", 885, { renders: [] });
    const asked = new Set(["casual|ar"]);
    expect(comboWaiting(asked, one, "casual", "ar", false)).toBe(true);
    expect(comboWaiting(asked, one, "casual", "ar", true)).toBe(false);       // ended: it isn't coming any more
    expect(comboWaiting(new Set(), one, "casual", "ar", false)).toBe(false);
    expect(comboWaiting(asked, item("goal-885", 885, { renders: [r("casual", "ar", "نص")] }), "casual", "ar", false)).toBe(false);
  });
});

describe("reduce: the live pace and the desk's steps", () => {
  const pace = (t: number, speed: number, holding: string[]) => ({ t, speed, holding });
  const step = (moment_id: string, s: string, t: number) => ({ moment_id, step: s, t });

  it("keeps the latest pace and drops it at the end", () => {
    let s = reduce(withMatch(), msg(1, "pace", pace(885, 1, ["goal-885"])));
    expect(s.pace).toEqual(pace(885, 1, ["goal-885"]));
    expect(s.clock).toBe(885);
    s = reduce(s, msg(2, "end", { reason: "full_time" }));
    expect(s.pace).toBeNull();
  });

  it("keeps each moment's steps once, in order", () => {
    let s = reduce(withMatch(), msg(1, "step", step("goal-885", "analyst", 890)));
    s = reduce(s, msg(2, "step", step("goal-885", "tactical", 895)));
    s = reduce(s, msg(3, "step", step("goal-885", "tactical", 896)));
    expect(s.steps["goal-885"].map((x) => x.step)).toEqual(["analyst", "tactical"]);
    expect(s.clock).toBe(896);
  });

  it("a reconnect burst ends on the latest pace", () => {
    const burst = [
      msg(0, "match", { ...info, mode: "live" }), msg(1, "thinking", moment("goal-885")),
      msg(2, "pace", pace(885, 1, ["goal-885"])), msg(3, "step", step("goal-885", "analyst", 900)),
      msg(4, "step", step("goal-885", "publish", 941)), msg(5, "feed", item("goal-885")),
      msg(6, "pace", pace(942, 6, [])),
    ];
    const s = burst.reduce(reduce, initialDesk);
    expect(s.pace).toEqual(pace(942, 6, []));
    expect(s.thinking).toEqual([]);
  });
});
