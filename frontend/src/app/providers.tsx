"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { SidebarProvider, useSidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from "@/lib/sidebar";
import Sidebar from "@/components/Sidebar";
import Spinner from "@/components/Spinner";

function MobileHeader() {
  const { toggle } = useSidebar();
  return (
    <header className="sticky top-0 z-10 flex h-14 items-center border-b border-border bg-card px-4 md:hidden">
      <button
        onClick={toggle}
        className="rounded-md p-1.5 text-secondary transition-colors hover:bg-card-alt hover:text-primary"
        aria-label="Open menu"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>
      <span className="ml-3 text-sm font-semibold text-primary">
        bahtzang<span className="text-accent">.trader</span>
      </span>
    </header>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const { expanded, mobile } = useSidebar();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const showSidebar = user && pathname !== "/login";

  if (!showSidebar) {
    return <main>{children}</main>;
  }

  return (
    <>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:outline-none">
        Skip to main content
      </a>
      <Sidebar />
      <main
        id="main-content"
        className="min-h-screen transition-[margin-left] duration-200"
        style={{ marginLeft: mobile ? 0 : (expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED) }}
      >
        {mobile && <MobileHeader />}
        {children}
      </main>
    </>
  );
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <SidebarProvider>
          <AppShell>{children}</AppShell>
        </SidebarProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
