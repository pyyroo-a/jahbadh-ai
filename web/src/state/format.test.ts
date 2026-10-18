import { describe, expect, it } from "vitest";
import { info, metric as make } from "../test-fixtures";
import { formatMetric } from "./format";

const metric = (name: string, subject: string, value: number | null, unit: string, window: [number, number] = [3600, 4500]) =>
  make(name, subject, {}, value, unit, window);
const tilt = metric("field_tilt", "NBR", 0.5, "share");

describe("formatMetric", () => {
  it("formats a missing value as no data", () => {
    expect(formatMetric({ ...tilt, value: null }, info).value).toBe("no data");
    expect(formatMetric({ ...tilt, value: 0.539 }, info).value).toBe("54%");
  });

  it("writes each unit the way the desk does", () => {
    expect(formatMetric(metric("xg_total", "NBR", 1.9096, "xG"), info).value).toBe("1.91");
    expect(formatMetric(metric("player_impact", "RMU-33", 3.6, "xGI"), info).value).toBe("3.60");
    expect(formatMetric(metric("ppda", "RMU", 17, "passes/def_action"), info).value).toBe("17.0");
    expect(formatMetric(metric("line_height", "NBR", 29.198, "m"), info).value).toBe("29.2 m");
    expect(formatMetric(metric("shot_map", "NBR", 15, "shots"), info).value).toBe("15");
    expect(formatMetric(metric("momentum", "MATCH", 0.216, "home_share"), info).value).toBe("22%");
    expect(formatMetric(metric("zone_overloads", "NBR", 0.321, "share_of_seconds"), info).value).toBe("32%");
    expect(formatMetric(metric("pass_quality", "NBR-10", 0.178, "difficulty"), info).value).toBe("0.18");
  });

  it("names the metric, who it's about and when", () => {
    expect(formatMetric(tilt, info)).toEqual({ value: "50%", label: "Field tilt", sub: "Northbridge FC · 61' to 75'" });
    expect(formatMetric(metric("player_impact", "RMU-33", 1, "xGI", [0, 886]), info).sub).toBe("Player 33 · 1' to 15'");
    expect(formatMetric(metric("momentum", "MATCH", 0.2, "home_share", [901, 1501]), info))
      .toEqual({ value: "20%", label: "Momentum (home share)", sub: "Both teams · 16' to 26'" });
    expect(formatMetric(metric("player_impact_change", "RMU-33", 0.5, "xGI"), info).label).toBe("player impact change");
  });
});
