"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

/**
 * 016-fix: Reusable hook for API data fetching with loading/error state.
 * Replaces the repeated useEffect + useState pattern across pages.
 */
export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  initialValue: T,
) {
  const { user } = useAuth();
  const [data, setData] = useState<T>(initialValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    fetcher()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // fetcher identity is caller's responsibility (use useCallback if dynamic)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  return { data, loading, error };
}
