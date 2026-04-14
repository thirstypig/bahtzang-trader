"use client";

import { createContext, useContext, useState } from "react";

interface SidebarContextValue {
  expanded: boolean;
  setExpanded: (v: boolean) => void;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue>({
  expanded: true,
  setExpanded: () => {},
  toggle: () => {},
});

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <SidebarContext.Provider value={{ expanded, setExpanded, toggle: () => setExpanded((e) => !e) }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  return useContext(SidebarContext);
}
