"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

export const SIDEBAR_WIDTH_EXPANDED = 240;
export const SIDEBAR_WIDTH_COLLAPSED = 68;

interface SidebarContextValue {
  expanded: boolean;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("sidebar") !== "collapsed";
  });

  const toggle = useCallback(() => {
    setExpanded((e) => {
      const next = !e;
      localStorage.setItem("sidebar", next ? "expanded" : "collapsed");
      return next;
    });
  }, []);

  const value = useMemo(() => ({ expanded, toggle }), [expanded, toggle]);

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar(): SidebarContextValue {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be used within a SidebarProvider");
  return ctx;
}
