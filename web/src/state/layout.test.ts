import { describe, expect, it } from "vitest";
import { layoutFor } from "./layout";

describe("layoutFor", () => {
  it("gives each persona its own layout", () => {
    expect(layoutFor("casual")).toBe("fan");
    expect(layoutFor("pundit")).toBe("analyst");
    expect(layoutFor("fantasy")).toBe("watch");
  });
});
