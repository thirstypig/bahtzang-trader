"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getRecentErrors, getErrorByRef, ErrorSummary, ErrorDetail } from "@/lib/api";
import Spinner from "@/components/Spinner";
import { getTimezone } from "@/lib/utils";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function ErrorsPage() {
  const { user } = useAuth();
  const [errors, setErrors] = useState<ErrorSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [detail, setDetail] = useState<ErrorDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    getRecentErrors(50)
      .then((data) => {
        setErrors(data.errors);
        setTotal(data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  async function handleSelectError(ref: string) {
    if (selectedRef === ref) {
      setSelectedRef(null);
      setDetail(null);
      return;
    }
    setSelectedRef(ref);
    setDetailLoading(true);
    try {
      const d = await getErrorByRef(ref);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  if (!user) return null;
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">Error Log</h1>
        <p className="mt-1 text-sm text-muted">
          {total} errors in buffer (last 100 kept) — click any error to see the full stack trace
        </p>
      </div>

      {errors.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <p className="text-accent text-sm font-medium">No errors recorded</p>
          <p className="mt-1 text-xs text-muted">Errors from /run and other endpoints will appear here</p>
        </div>
      ) : (
        <div className="space-y-2">
          {errors.map((err) => (
            <div key={err.ref}>
              <button
                onClick={() => handleSelectError(err.ref)}
                className={`w-full rounded-xl border bg-card px-5 py-3 text-left transition-colors hover:border-border-strong ${
                  selectedRef === err.ref ? "border-red-800" : "border-border"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="shrink-0 rounded bg-red-900/40 px-2 py-0.5 text-[10px] font-bold text-red-400 font-mono">
                    {err.ref}
                  </span>
                  <span className="shrink-0 rounded bg-card-alt px-2 py-0.5 text-[10px] font-semibold uppercase text-secondary">
                    {err.error_code}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm text-secondary">
                    {err.message}
                  </span>
                  <span className="shrink-0 text-[10px] text-muted">
                    {err.method} {err.path}
                  </span>
                  <span className="shrink-0 text-[10px] text-muted">
                    {timeAgo(err.timestamp)}
                  </span>
                </div>
              </button>

              {selectedRef === err.ref && (
                <div className="mt-1 rounded-lg border border-red-900/30 bg-surface p-4">
                  {detailLoading ? (
                    <p className="text-xs text-muted">Loading stack trace...</p>
                  ) : detail ? (
                    <>
                      <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-muted">Type:</span>{" "}
                          <span className="text-secondary">{detail.error_type}</span>
                        </div>
                        <div>
                          <span className="text-muted">Code:</span>{" "}
                          <span className="text-secondary">{detail.error_code}</span>
                        </div>
                        <div>
                          <span className="text-muted">Path:</span>{" "}
                          <span className="text-secondary">{detail.method} {detail.path}</span>
                        </div>
                        <div>
                          <span className="text-muted">Time:</span>{" "}
                          <span className="text-secondary">{new Date(detail.timestamp).toLocaleString("en-US", { timeZone: getTimezone() })}</span>
                        </div>
                      </div>
                      <p className="mb-3 text-sm text-red-400">{detail.message}</p>
                      <details open>
                        <summary className="cursor-pointer text-xs text-muted hover:text-secondary">
                          Stack Trace
                        </summary>
                        <pre className="mt-2 max-h-64 overflow-auto rounded bg-card p-3 text-[11px] leading-relaxed text-secondary font-mono">
                          {detail.stack}
                        </pre>
                      </details>
                    </>
                  ) : (
                    <p className="text-xs text-muted">Error detail not found</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
