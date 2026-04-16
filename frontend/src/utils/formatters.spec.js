import { describe, expect, it } from "vitest";

import { fmtVol } from "./formatters";

describe("formatters", () => {
  it("renders zero volume as 0 instead of an empty placeholder", () => {
    expect(fmtVol(0)).toBe("0");
  });

  it("renders missing volume as an empty placeholder", () => {
    expect(fmtVol(null)).toBe("\u2014");
  });
});
