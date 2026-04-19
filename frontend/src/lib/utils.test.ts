import { describe, it, expect } from "vitest";
import { formatCurrency, formatDateTime, formatDate } from "./utils";

describe("formatCurrency", () => {
  it("formats positive amounts", () => {
    expect(formatCurrency(1234.56)).toBe("$1,234.56");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0.00");
  });

  it("formats negative amounts", () => {
    expect(formatCurrency(-500)).toBe("-$500.00");
  });

  it("formats large amounts with commas", () => {
    expect(formatCurrency(1000000)).toBe("$1,000,000.00");
  });

  it("rounds to 2 decimal places", () => {
    expect(formatCurrency(99.999)).toBe("$100.00");
  });

  it("handles small fractional amounts", () => {
    expect(formatCurrency(0.01)).toBe("$0.01");
  });
});

describe("formatDateTime", () => {
  it("formats ISO date strings", () => {
    const result = formatDateTime("2026-04-18T14:30:00Z");
    // Should include month, day, year, and time
    expect(result).toMatch(/Apr/);
    expect(result).toMatch(/2026/);
  });
});

describe("formatDate", () => {
  it("formats ISO date strings without time", () => {
    const result = formatDate("2026-04-18T14:30:00Z");
    expect(result).toMatch(/Apr/);
    expect(result).toMatch(/2026/);
    // Should NOT include time components
    expect(result).not.toMatch(/:/);
  });
});
