import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setApiToken, getPortfolios, getPortfolioDetail, createPortfolio, deletePortfolio, runPortfolio } from "./api";

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
      await getPortfolios();
      expect(mockFetch).toHaveBeenCalledOnce();
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBe("Bearer test-token");
    });

    it("omits auth header when token is null", async () => {
      setApiToken(null);
      mockFetch.mockResolvedValue(mockResponse([]));
      await getPortfolios();
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBeUndefined();
    });
  });

  describe("error handling", () => {
    it("throws with detail message from API", async () => {
      mockFetch.mockResolvedValue(
        mockResponse({ detail: "Portfolio not found" }, 404),
      );
      await expect(getPortfolioDetail(999)).rejects.toThrow("Portfolio not found");
    });

    it("throws with structured error from API", async () => {
      mockFetch.mockResolvedValue(
        mockResponse(
          { detail: { error_code: "BUDGET_EXCEEDED", message: "Over budget" } },
          400,
        ),
      );
      await expect(
        createPortfolio({
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
      await expect(getPortfolios()).rejects.toThrow("Internal Server Error");
    });
  });

  describe("getPortfolios", () => {
    it("fetches portfolio list", async () => {
      const portfolios = [{ id: 1, name: "Growth" }];
      mockFetch.mockResolvedValue(mockResponse(portfolios));
      const result = await getPortfolios();
      expect(result).toEqual(portfolios);
      expect(mockFetch.mock.calls[0][0]).toMatch(/\/portfolios$/);
    });
  });

  describe("getPortfolioDetail", () => {
    it("fetches single portfolio with trades", async () => {
      const portfolio = { id: 1, name: "Growth", trades: [] };
      mockFetch.mockResolvedValue(mockResponse(portfolio));
      const result = await getPortfolioDetail(1);
      expect(result).toEqual(portfolio);
      expect(mockFetch.mock.calls[0][0]).toMatch(/\/portfolios\/1$/);
    });
  });

  describe("createPortfolio", () => {
    it("sends POST with portfolio data", async () => {
      const portfolio = { id: 1, name: "Income", budget: 5000 };
      mockFetch.mockResolvedValue(mockResponse(portfolio));
      const result = await createPortfolio({
        name: "Income",
        budget: 5000,
        trading_goal: "steady_income",
      });
      expect(result).toEqual(portfolio);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/portfolios$/);
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body)).toMatchObject({
        name: "Income",
        budget: 5000,
        trading_goal: "steady_income",
      });
    });
  });

  describe("deletePortfolio", () => {
    it("sends DELETE request", async () => {
      mockFetch.mockResolvedValue(mockResponse({}));
      await deletePortfolio(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/portfolios\/1$/);
      expect(options.method).toBe("DELETE");
    });
  });

  describe("runPortfolio", () => {
    it("sends POST and uses 45s timeout", async () => {
      const result = { action: "buy", ticker: "AAPL", executed: true };
      mockFetch.mockResolvedValue(mockResponse(result));
      const r = await runPortfolio(1);
      expect(r).toEqual(result);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/portfolios\/1\/run$/);
      expect(options.method).toBe("POST");
      // Should have a longer timeout than default 15s
      expect(options.signal).toBeDefined();
    });
  });
});
