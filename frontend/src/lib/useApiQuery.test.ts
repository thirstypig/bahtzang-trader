import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useApiQuery } from "./useApiQuery";

// Mock useAuth to return a user by default
const mockUser = { email: "test@example.com", name: "Test", picture: "" };
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: mockUser, loading: false, denied: false, signIn: vi.fn(), signOut: vi.fn() })),
}));

import { useAuth } from "@/lib/auth";
const mockUseAuth = vi.mocked(useAuth);

beforeEach(() => {
  mockUseAuth.mockReturnValue({
    user: mockUser,
    loading: false,
    denied: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  });
});

describe("useApiQuery", () => {
  it("returns loading=true initially", () => {
    const fetcher = vi.fn(() => new Promise<string[]>(() => {})); // never resolves
    const { result } = renderHook(() => useApiQuery(fetcher, []));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("returns data after successful fetch", async () => {
    const data = [{ id: 1, name: "item" }];
    const fetcher = vi.fn().mockResolvedValue(data);

    const { result } = renderHook(() => useApiQuery(fetcher, []));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.data).toEqual(data);
    expect(result.current.error).toBeNull();
  });

  it("returns error on failed fetch", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useApiQuery(fetcher, []));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe("Network error");
    expect(result.current.data).toEqual([]);
  });

  it("does not fetch when user is null", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      denied: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    });
    const fetcher = vi.fn().mockResolvedValue("data");

    const { result } = renderHook(() => useApiQuery(fetcher, "initial"));

    // Give it a tick to confirm it doesn't call the fetcher
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(fetcher).not.toHaveBeenCalled();
    // loading remains true because the effect never ran to set it false
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe("initial");
  });

  it("refetches when user changes (deps change)", async () => {
    const fetcher = vi.fn().mockResolvedValue("first");

    const { result, rerender } = renderHook(() => useApiQuery(fetcher, "init"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.data).toBe("first");
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Simulate user changing — the hook depends on [user]
    fetcher.mockResolvedValue("second");
    const newUser = { email: "other@example.com", name: "Other", picture: "" };
    mockUseAuth.mockReturnValue({
      user: newUser,
      loading: false,
      denied: false,
      signIn: vi.fn(),
      signOut: vi.fn(),
    });

    rerender();

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2);
    });
    expect(result.current.data).toBe("second");
  });
});
