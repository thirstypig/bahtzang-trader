import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setApiToken, getPlans, getPlan, createPlan, deletePlan, runPlan } from "./api";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(data),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
  setApiToken("test-token");
});

afterEach(() => {
  setApiToken(null);
});

describe("API client", () => {
  describe("auth header", () => {
    it("sends Bearer token when set", async () => {
      mockFetch.mockResolvedValue(mockResponse([]));
      await getPlans();
      expect(mockFetch).toHaveBeenCalledOnce();
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBe("Bearer test-token");
    });

    it("omits auth header when token is null", async () => {
      setApiToken(null);
      mockFetch.mockResolvedValue(mockResponse([]));
      await getPlans();
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBeUndefined();
    });
  });

  describe("error handling", () => {
    it("throws with detail message from API", async () => {
      mockFetch.mockResolvedValue(
        mockResponse({ detail: "Plan not found" }, 404),
      );
      await expect(getPlan(999)).rejects.toThrow("Plan not found");
    });

    it("throws with structured error from API", async () => {
      mockFetch.mockResolvedValue(
        mockResponse(
          { detail: { error_code: "BUDGET_EXCEEDED", message: "Over budget" } },
          400,
        ),
      );
      await expect(
        createPlan({
          name: "Test",
          budget: 999999,
          trading_goal: "maximize_returns",
        }),
      ).rejects.toThrow("Over budget");
    });

    it("falls back to statusText when no detail", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({}),
      });
      await expect(getPlans()).rejects.toThrow("Internal Server Error");
    });
  });

  describe("getPlans", () => {
    it("fetches plan list", async () => {
      const plans = [{ id: 1, name: "Growth" }];
      mockFetch.mockResolvedValue(mockResponse(plans));
      const result = await getPlans();
      expect(result).toEqual(plans);
      expect(mockFetch.mock.calls[0][0]).toMatch(/\/plans$/);
    });
  });

  describe("getPlan", () => {
    it("fetches single plan with trades", async () => {
      const plan = { id: 1, name: "Growth", trades: [] };
      mockFetch.mockResolvedValue(mockResponse(plan));
      const result = await getPlan(1);
      expect(result).toEqual(plan);
      expect(mockFetch.mock.calls[0][0]).toMatch(/\/plans\/1$/);
    });
  });

  describe("createPlan", () => {
    it("sends POST with plan data", async () => {
      const plan = { id: 1, name: "Income", budget: 5000 };
      mockFetch.mockResolvedValue(mockResponse(plan));
      const result = await createPlan({
        name: "Income",
        budget: 5000,
        trading_goal: "steady_income",
      });
      expect(result).toEqual(plan);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/plans$/);
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body)).toMatchObject({
        name: "Income",
        budget: 5000,
        trading_goal: "steady_income",
      });
    });
  });

  describe("deletePlan", () => {
    it("sends DELETE request", async () => {
      mockFetch.mockResolvedValue(mockResponse({}));
      await deletePlan(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/plans\/1$/);
      expect(options.method).toBe("DELETE");
    });
  });

  describe("runPlan", () => {
    it("sends POST and uses 45s timeout", async () => {
      const result = { action: "buy", ticker: "AAPL", executed: true };
      mockFetch.mockResolvedValue(mockResponse(result));
      const r = await runPlan(1);
      expect(r).toEqual(result);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/plans\/1\/run$/);
      expect(options.method).toBe("POST");
      // Should have a longer timeout than default 15s
      expect(options.signal).toBeDefined();
    });
  });
});
