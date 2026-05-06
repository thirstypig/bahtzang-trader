"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import TopNav from "@/components/TopNav";
import Spinner from "@/components/Spinner";

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const showNav = user && pathname !== "/login";

  if (!showNav) {
    return <main>{children}</main>;
  }

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:outline-none"
      >
        Skip to main content
      </a>
      <TopNav />
      <main id="main-content" className="mx-auto min-h-screen max-w-7xl pt-14">
        {children}
      </main>
    </>
  );
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppShell>{children}</AppShell>
      </AuthProvider>
    </ThemeProvider>
  );
}
