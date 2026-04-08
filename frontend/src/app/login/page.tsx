"use client";

import { useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-lg font-bold text-white">
              B
            </div>
            <h1 className="text-xl font-bold text-white">
              bahtzang<span className="text-emerald-400">.trader</span>
            </h1>
            <p className="mt-2 text-sm text-zinc-500">
              Sign in to access your trading dashboard
            </p>
          </div>

          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={async (response) => {
                setError(null);
                try {
                  await login(response.credential!);
                } catch (err) {
                  setError(
                    err instanceof Error ? err.message : "Login failed"
                  );
                }
              }}
              onError={() => setError("Google sign-in failed")}
              theme="filled_black"
              size="large"
              width="300"
            />
          </div>

          {error && (
            <div className="mt-4 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
              <p className="text-center text-sm text-red-400">{error}</p>
            </div>
          )}

          <p className="mt-6 text-center text-xs text-zinc-600">
            Access restricted to authorized accounts only
          </p>
        </div>
      </div>
    </div>
  );
}
