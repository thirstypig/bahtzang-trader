"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";
import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import Navbar from "@/components/Navbar";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  // Show a loading spinner while checking auth
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />
      </div>
    );
  }

  // Don't show navbar on login page
  const showNavbar = user && pathname !== "/login";

  return (
    <>
      {showNavbar && <Navbar />}
      <main>{children}</main>
    </>
  );
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthProvider>
        <AppShell>{children}</AppShell>
      </AuthProvider>
    </GoogleOAuthProvider>
  );
}
