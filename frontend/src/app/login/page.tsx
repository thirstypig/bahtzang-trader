"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

export default function LoginPage() {
  const { signIn, denied } = useAuth();
  const { theme, toggle } = useTheme();
  const [loading, setLoading] = useState(false);

  const themeButton = (
    <button
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="bz-glass-soft fixed right-6 top-6 rounded-full p-2 text-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      {theme === "dark" ? (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
        </svg>
      ) : (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
        </svg>
      )}
    </button>
  );

  if (denied) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        {themeButton}
        <div className="w-full max-w-md text-center">
          <div className="bz-glass-strong p-10">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-neg/15">
              <svg className="h-8 w-8 text-neg" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-primary">Access Denied</h1>
            <p className="mt-4 text-lg text-secondary">
              Sorry — you are not permitted.
            </p>
            <p className="mt-2 text-lg font-semibold text-muted">
              Go away. This is a private site.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="bz-glass-soft mt-8 px-6 py-2.5 text-sm font-medium text-secondary transition-colors hover:text-primary"
            >
              Try a different account
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      {themeButton}

      <div className="w-full max-w-sm">
        <div className="bz-glass-strong p-8">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-accent text-lg font-bold text-white shadow-lg shadow-accent/20">
              B
            </div>
            <h1 className="text-xl font-bold text-primary">
              bahtzang<span className="bz-gradient-text">.trader</span>
            </h1>
            <p className="mt-2 text-sm text-muted">
              Sign in to access your trading dashboard
            </p>
          </div>

          <button
            onClick={() => {
              setLoading(true);
              signIn();
            }}
            disabled={loading}
            className="bz-glass-soft flex w-full items-center justify-center gap-3 px-4 py-3 text-sm font-medium text-primary transition-colors hover:text-primary disabled:opacity-50"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            {loading ? "Redirecting to Google..." : "Sign in with Google"}
          </button>

          <p className="mt-6 text-center text-xs text-muted">
            Access restricted to authorized accounts only
          </p>
        </div>
      </div>
    </div>
  );
}
