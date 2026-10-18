import { describe, expect, it } from "vitest";
import type { Claim, EventLine, FeedItem, Metric, Rejection } from "../api/types";
import { evidenceCount, evidenceOf, rejectionStatus } from "./evidence";

const ev = (id: number): EventLine => ({
  id, t: id, minute: 1, type: "PASS", team_id: "NBR", player_id: null, related_player_id: null, x: 0, y: 0,
  end_x: null, end_y: null, outcome: true, xg: null, lines: { en: "", ar: "", es: "" },
});
const metric = (id: string): Metric => ({
  id, name: id.split(":")[0], subject: "NBR", window: [0, 600], value: 0.5, unit: "share", evidence_event_ids: [],
  evidence_frames: null, data: {}, note: null,
});
const claim = (id: string, event_ids: number[], metric_ids: string[]): Claim =>
  ({ id, text: "words", event_ids, metric_ids, figures: [] });
const item = (claims: Claim[], metrics: Metric[] = []): FeedItem => ({
  moment: { id: "m", kind: "goal", t: 885, team_id: null, player_id: null, event_ids: [], label: "goal" },
  claims, renders: [], rejections: [], metrics, stats: {}, latency_s: 1,
});
const rej = (claim_id: string, layer: Rejection["layer"], persona: Rejection["persona"] = null): Rejection =>
  ({ claim_id, text: "draft", layer, reasons: ["why"], attempt: 0, persona, language: null });

describe("evidence", () => {
  it("lists a claim's evidence in order and skips events not streamed yet", () => {
    const c = claim("c1", [9, 3, 400], ["field_tilt:NBR:0-600", "ppda:RMU:0-600", "missing:x"]);
    const it_ = item([c], [metric("ppda:RMU:0-600"), metric("field_tilt:NBR:0-600")]);
    const got = evidenceOf(it_, c, { 3: ev(3), 9: ev(9) });
    expect(got.events.map((e) => e.id)).toEqual([9, 3]);
    expect(got.metrics.map((m) => m.id)).toEqual(["field_tilt:NBR:0-600", "ppda:RMU:0-600"]);
    expect(evidenceCount(c)).toBe(6);
  });

  it("labels a rejection by what happened next", () => {
    const published = item([claim("m:c1", [], [])]);
    expect(rejectionStatus(published, rej("m:c1", "semantic"))).toBe("rewritten");
    expect(rejectionStatus(published, rej("m:c2", "deterministic"))).toBe("dropped");
    expect(rejectionStatus(published, rej("m:c1", "persona", "fantasy"))).toBe("fell back");
    expect(rejectionStatus(published, { ...rej("m:c1", "localization", "pundit"), language: "ar" })).toBe("fell back");
  });
});
