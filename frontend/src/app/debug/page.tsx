"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getSupabase } from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4060";

export default function DebugPage() {
  const { user, accessToken } = useAuth();
  const [sessionInfo, setSessionInfo] = useState<string>("Loading...");
  const [debugResult, setDebugResult] = useState<string>("");

  useEffect(() => {
    getSupabase()
      .auth.getSession()
      .then(({ data: { session } }) => {
        setSessionInfo(
          JSON.stringify(
            {
              hasSession: !!session,
              hasAccessToken: !!session?.access_token,
              tokenLength: session?.access_token?.length || 0,
              tokenStart: session?.access_token?.substring(0, 30) || "null",
              email: session?.user?.email || "none",
              expiresAt: session?.expires_at,
            },
            null,
            2
          )
        );

        // Send token to backend debug endpoint
        if (session?.access_token) {
          fetch(`${API}/auth/debug`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: session.access_token }),
          })
            .then((r) => r.json())
            .then((data) => setDebugResult(JSON.stringify(data, null, 2)))
            .catch((e) => setDebugResult(`Fetch error: ${e.message}`));
        } else {
          setDebugResult("No token to test");
        }
      });
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-2xl font-bold text-white">Auth Debug</h1>

      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-sm font-medium text-zinc-400">Auth Context</h2>
        <pre className="mt-2 text-xs text-emerald-400">
          user: {user ? user.email : "null"}
          {"\n"}accessToken from context: {accessToken ? `${accessToken.substring(0, 30)}...` : "null"}
        </pre>
      </div>

      <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-sm font-medium text-zinc-400">Supabase Session</h2>
        <pre className="mt-2 overflow-auto text-xs text-zinc-300">{sessionInfo}</pre>
      </div>

      <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="text-sm font-medium text-zinc-400">Backend JWT Debug</h2>
        <pre className="mt-2 overflow-auto text-xs text-zinc-300">{debugResult}</pre>
      </div>
    </div>
  );
}
