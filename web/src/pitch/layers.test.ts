import { describe, expect, it } from "vitest";
import type { EventLine } from "../api/types";
import { info, metric } from "../test-fixtures";
import { WIDTH, zoneRect } from "./coords";
import { eventLayer, metricLayer } from "./layers";

const heat = metric("heatmap", "RMU-33", { grid: [], cells: [21, 14], samples: 0 }, 0, "samples");

describe("metricLayer", () => {
  it("draws nothing for an empty heatmap", () => {
    expect(metricLayer({ ...heat, value: null, data: { cells: [21, 14] } }, info)).toEqual({ kind: "none" });
  });

  it("draws only the heatmap cells a player stood in, on their side of the pitch", () => {
    const grid = Array.from({ length: 21 }, () => Array(14).fill(0));
    grid[20][13] = 0.25;                                    // the away player's attacking corner: far end, their left
    const layer = metricLayer({ ...heat, value: 4, data: { grid, cells: [21, 14], samples: 4 } }, info);
    expect(layer.kind).toBe("heat");
    if (layer.kind !== "heat") return;
    expect(layer.cells).toHaveLength(1);
    const c = layer.cells[0];
    expect([c.x, c.w, c.v]).toEqual([0, 5, 0.25]);           // flipped to the left end of the broadcast pitch
    expect(c.y).toBeCloseTo(WIDTH - WIDTH / 14);              // and to the bottom edge
    expect(c.h).toBeCloseTo(WIDTH / 14);
  });

  it("skips network edges whose nodes are missing", () => {
    const net = metric("pass_network", "NBR", {
      nodes: {
        "NBR-9": { pos: [60, 30], passes: 5, received: 2 }, "NBR-10": { pos: [70, 40], passes: 2, received: 4 },
        "NBR-4": { pos: null, passes: 0, received: 3 },
      },
      edges: [["NBR-9", "NBR-10", 4], ["NBR-9", "NBR-77", 3], ["NBR-9", "NBR-4", 3]],
    });
    const layer = metricLayer(net, info);
    expect(layer.kind).toBe("network");
    if (layer.kind !== "network") return;
    expect(layer.nodes.map((n) => n.label)).toEqual(["9", "10"]);
    expect(layer.edges).toEqual([{ x1: 60, y1: 38, x2: 70, y2: 28, count: 4, team: "NBR" }]);
  });

  it("puts average positions and shots in team colours on the broadcast pitch", () => {
    const shape = metricLayer(metric("average_positions", "RMU", { players: { "RMU-33": [90, 50] } }), info);
    expect(shape).toEqual({ kind: "dots", dots: [{ x: 15, y: 50, label: "33", team: "RMU" }] });
    const shots = metricLayer(metric("shot_map", "NBR", { shots: { 21: { x: 100, y: 30, xg: 0.4, goal: true } } }), info);
    expect(shots).toEqual({ kind: "shots", shots: [{ x: 100, y: 38, xg: 0.4, goal: true, team: "NBR" }] });
  });

  it("labels an overload zone and ignores metrics with nothing to draw", () => {
    const zone = metricLayer(metric("zone_overloads", "NBR", { zone: "middle-centre", typical: "3v1" }), info);
    expect(zone).toEqual({ kind: "zone", rect: zoneRect("middle-centre", true), label: "3v1" });
    expect(metricLayer(metric("momentum", "MATCH"), info)).toEqual({ kind: "none" });
    expect(metricLayer(metric("heatmap", "XYZ-1", { grid: [[1]], cells: [21, 14] }), info)).toEqual({ kind: "none" });
  });
});

describe("eventLayer", () => {
  const ev = (id: number, type: EventLine["type"], end: [number, number] | null): EventLine => ({
    id, t: id, minute: 1, type, team_id: "NBR", player_id: null, related_player_id: null, x: 50, y: 60,
    end_x: end?.[0] ?? null, end_y: end?.[1] ?? null, outcome: true, xg: null, lines: { en: "", ar: "", es: "" },
  });

  it("turns passes into arrows and the rest into points", () => {
    const { arrows, points } = eventLayer([ev(1, "PASS", [70, 40]), ev(2, "SHOT", null), ev(3, "PASS", null)]);
    expect(arrows).toEqual([{ id: 1, x1: 50, y1: 8, x2: 70, y2: 28 }]);
    expect(points.map((p) => [p.id, p.x, p.y])).toEqual([[2, 50, 8], [3, 50, 8]]);
  });
});
