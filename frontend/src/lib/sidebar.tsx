"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export const SIDEBAR_WIDTH_EXPANDED = 240;
export const SIDEBAR_WIDTH_COLLAPSED = 68;
const MOBILE_BREAKPOINT = 768;

interface SidebarContextValue {
  expanded: boolean;
  mobile: boolean;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [mobile, setMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < MOBILE_BREAKPOINT;
  });

  const [expanded, setExpanded] = useState(() => {
    if (typeof window === "undefined") return true;
    if (window.innerWidth < MOBILE_BREAKPOINT) return false;
    return localStorage.getItem("sidebar") !== "collapsed";
  });

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    setMobile(mq.matches);
    if (mq.matches) setExpanded(false);
    const handler = (e: MediaQueryListEvent) => {
      setMobile(e.matches);
      if (e.matches) setExpanded(false);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggle = useCallback(() => {
    setExpanded((e) => {
      const next = !e;
      if (!mobile) {
        localStorage.setItem("sidebar", next ? "expanded" : "collapsed");
      }
      return next;
    });
  }, [mobile]);

  const value = useMemo(() => ({ expanded, mobile, toggle }), [expanded, mobile, toggle]);

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
