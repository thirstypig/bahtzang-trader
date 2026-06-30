"use client";

import { useCallback, useRef, useState } from "react";
import { getCompanyProfile } from "@/lib/api";
import { CompanyProfile } from "@/lib/types";

/** Market cap arrives in millions USD; render it compactly ($3.2T, $250B, $800M). */
function formatMarketCap(millions: number | null): string | null {
  if (millions == null || millions <= 0) return null;
  if (millions >= 1_000_000) return `$${(millions / 1_000_000).toFixed(1)}T`;
  if (millions >= 1_000) return `$${(millions / 1_000).toFixed(1)}B`;
  return `$${Math.round(millions)}M`;
}

interface TickerProps {
  symbol: string | null | undefined;
  className?: string;
}

/**
 * Renders a stock/crypto symbol. On hover or keyboard focus it lazily fetches
 * the company profile (once) and shows a card with a Yahoo Finance link.
 */
export default function Ticker({ symbol, className = "" }: TickerProps) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const fetched = useRef(false);

  const load = useCallback(async () => {
    if (fetched.current || !symbol) return;
    fetched.current = true;
    setLoading(true);
    try {
      setProfile(await getCompanyProfile(symbol));
    } catch {
      // Fall back to a Yahoo-only card so the link still works.
      setProfile({
        ticker: symbol,
        name: null,
        industry: null,
        exchange: null,
        market_cap: null,
        logo: null,
        currency: null,
        website: null,
        yahoo_url: `https://finance.yahoo.com/quote/${symbol.replace("/", "-")}`,
        source: "none",
      });
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  if (!symbol) return <span className="text-muted">—</span>;

  const show = () => {
    setOpen(true);
    load();
  };
  const hide = () => setOpen(false);
  const marketCap = formatMarketCap(profile?.market_cap ?? null);

  return (
    <span
      className="group/ticker relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span
        tabIndex={0}
        aria-label={`${symbol} company info`}
        className={`cursor-help font-mono font-semibold text-primary underline decoration-dotted decoration-muted underline-offset-4 outline-none ${className}`}
      >
        {symbol}
      </span>

      {open && (
        <span
          role="tooltip"
          className="bz-glass-soft absolute left-0 top-full z-50 mt-2 block w-64 max-w-[calc(100vw-2rem)] rounded-lg p-3 text-left text-xs leading-relaxed text-secondary shadow-lg"
        >
          <span className="flex items-center gap-2">
            {profile?.logo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={profile.logo}
                alt=""
                className="h-6 w-6 rounded bg-white object-contain"
              />
            )}
            <span className="font-semibold text-primary">
              {profile?.name || symbol}
            </span>
          </span>

          {loading && <span className="mt-1 block text-muted">Loading…</span>}

          {!loading && (
            <span className="mt-1 block space-y-0.5">
              {profile?.industry && (
                <span className="block">{profile.industry}</span>
              )}
              {profile?.exchange && (
                <span className="block text-muted">{profile.exchange}</span>
              )}
              {marketCap && (
                <span className="block text-muted">Market cap {marketCap}</span>
              )}
            </span>
          )}

          <a
            href={
              profile?.yahoo_url ||
              `https://finance.yahoo.com/quote/${symbol.replace("/", "-")}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 font-semibold text-accent hover:underline"
          >
            View on Yahoo Finance
            <svg
              className="h-3 w-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M7 17L17 7M17 7H8M17 7v9" />
            </svg>
          </a>
        </span>
      )}
    </span>
  );
}
