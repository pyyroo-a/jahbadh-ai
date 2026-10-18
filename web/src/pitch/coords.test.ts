import { describe, expect, it } from "vitest";
import { WIDTH, fromAttacking, toSvg, zoneRect } from "./coords";

describe("coords", () => {
  it("flips the away team onto the broadcast pitch", () => {
    expect(fromAttacking(90, 50, true)).toEqual([90, 50]);
    expect(fromAttacking(90, 50, false)).toEqual([15, 18]);
    expect(toSvg(10, 60)).toEqual([10, 8]);
  });

  it("places a zone from the attacking team's side", () => {
    expect(zoneRect("final-left", true)).toEqual({ x: 70, y: 0, w: 35, h: WIDTH / 3 });
    expect(zoneRect("final-left", false)).toEqual({ x: 0, y: (2 * WIDTH) / 3, w: 35, h: WIDTH / 3 });
    expect(zoneRect("middle-centre", true)).toEqual({ x: 35, y: WIDTH / 3, w: 35, h: WIDTH / 3 });
  });
});
