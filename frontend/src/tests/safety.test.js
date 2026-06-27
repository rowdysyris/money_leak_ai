import { describe, expect, it } from "vitest";
import { getFriendlyErrorMessage } from "../api/client";
import {
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
  getLeakScoreColor,
  getLeakScoreSeverity
} from "../utils/formatters";

describe("frontend safety helpers", () => {
  it("formats nullish and Indian currency values safely", () => {
    expect(formatCurrency(null)).toBe("₹0");
    expect(formatCurrency(undefined)).toBe("₹0");
    expect(formatCurrency(0)).toBe("₹0");
    expect(formatCurrency(1234567.89)).toBe("₹12,34,567.89");
  });

  it("formats missing dates, percentages, and numbers safely", () => {
    expect(formatDate(null)).toBe("-");
    expect(formatDate(undefined)).toBe("-");
    expect(formatDate("")).toBe("-");
    expect(formatPercent(null)).toBe("0%");
    expect(formatPercent(Number.NaN)).toBe("0%");
    expect(formatNumber(null)).toBe("0");
  });

  it("uses safe leak score defaults and thresholds", () => {
    expect(getLeakScoreColor(null)).toContain("green");
    expect(getLeakScoreColor(0)).toContain("green");
    expect(getLeakScoreColor(50)).toContain("yellow");
    expect(getLeakScoreColor(80)).toContain("red");
    expect(getLeakScoreSeverity(null)).toBe("Healthy");
  });

  it("returns controlled API error messages", () => {
    expect(getFriendlyErrorMessage({ code: "ECONNABORTED" })).toContain("took too long");
    expect(getFriendlyErrorMessage({ response: { status: 401 } })).toContain("Session expired");
    expect(getFriendlyErrorMessage({ response: { status: 403 } })).toContain("Access denied");
    expect(getFriendlyErrorMessage({ response: { status: 500 } })).toBe("Something went wrong. Please try again.");
    expect(getFriendlyErrorMessage({})).toContain("Could not connect");
  });
});
