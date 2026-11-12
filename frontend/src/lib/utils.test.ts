import { describe, expect, it } from "vitest";
import { fmtSignedR } from "@/lib/utils";

describe("fmtSignedR", () => {
  it("signs results and never shows a negative zero", () => {
    expect(fmtSignedR(2.6)).toBe("+2.6R");
    expect(fmtSignedR(-0.5)).toBe("-0.5R");
    expect(fmtSignedR(-0.04)).toBe("0.0R"); // was "-0.0R" on the Signals page
    expect(fmtSignedR(0.001, 2)).toBe("0.00R");
    expect(fmtSignedR(-55.0337, 2)).toBe("-55.03R");
    expect(fmtSignedR(null)).toBe("—");
  });
});
