import { describe, expect, it } from "vitest";
import type { Figure } from "../api/types";
import { figureSegments } from "./figures";

const fig = (written: string) => ({ metric_id: "m", field: "value", written }) as Figure;

describe("figureSegments", () => {
  it("marks each written figure once", () => {
    expect(figureSegments("RMU 3.67 to NBR 2.99, and 3.67 again", [fig("3.67"), fig("2.99")])).toEqual([
      { text: "RMU ", figure: false }, { text: "3.67", figure: true }, { text: " to NBR ", figure: false },
      { text: "2.99", figure: true }, { text: ", and 3.67 again", figure: false },
    ]);
  });

  it("doesn't mark a figure inside a longer number", () => {
    expect(figureSegments("PPDA 21.0 then 1.0", [fig("1.0")])).toEqual([
      { text: "PPDA 21.0 then ", figure: false }, { text: "1.0", figure: true },
    ]);
  });

  it("leaves a translated line unmarked when the figure isn't in it", () => {
    expect(figureSegments("كلمة كلمة", [fig("45%")])).toEqual([{ text: "كلمة كلمة", figure: false }]);
  });
});
