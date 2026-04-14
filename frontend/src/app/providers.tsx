"use client";

import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { SidebarProvider, useSidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from "@/lib/sidebar";
import Sidebar from "@/components/Sidebar";
import Spinner from "@/components/Spinner";

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const { expanded } = useSidebar();

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
      <Sidebar />
      <main
        className="min-h-screen transition-[margin-left] duration-200"
        style={{ marginLeft: expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED }}
      >
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
