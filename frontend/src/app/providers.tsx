"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import Navbar from "@/components/Navbar";

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-500" />
      </div>
    );
  }

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
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
