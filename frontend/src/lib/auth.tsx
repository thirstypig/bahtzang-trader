"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import { Session } from "@supabase/supabase-js";
import { setApiToken } from "./api";
import { getSupabase } from "./supabase";

interface User {
  email: string;
  name: string;
  picture: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  denied: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const ALLOWED_EMAIL = process.env.NEXT_PUBLIC_ALLOWED_EMAIL || "";

// 007-fix: Throw if used outside provider instead of silent no-op
const AuthContext = createContext<AuthContextType | null>(null);

function extractUser(session: Session | null): User | null {
  if (!session?.user) return null;
  const meta = session.user.user_metadata || {};
  return {
    email: session.user.email || "",
    name: meta.full_name || meta.name || "",
    picture: meta.avatar_url || meta.picture || "",
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    function applySession(session: Session | null) {
      const extracted = extractUser(session);
      if (extracted && ALLOWED_EMAIL && extracted.email !== ALLOWED_EMAIL) {
        setDenied(true);
        setUser(null);
        setApiToken(null);
        getSupabase().auth.signOut();
        setLoading(false);
        return;
      }
      setDenied(false);
      setUser(extracted);
      setApiToken(session?.access_token || null);
      setLoading(false);
    }

    // Check for existing session on mount
    getSupabase().auth.getSession().then(({ data: { session } }) => {
      applySession(session);
    });

    // Listen for auth state changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = getSupabase().auth.onAuthStateChange((_event, session) => {
      applySession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Redirect based on auth state
  useEffect(() => {
    if (loading) return;
    if (!user && pathname !== "/login") {
      router.replace("/login");
    } else if (user && pathname === "/login") {
      router.replace("/");
    }
  }, [user, loading, pathname, router]);

  const signIn = useCallback(async () => {
    await getSupabase().auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/`,
      },
    });
  }, []);

  const signOut = useCallback(async () => {
    await getSupabase().auth.signOut();
    setUser(null);
    setApiToken(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, denied, signIn, signOut }),
    [user, loading, denied, signIn, signOut],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
