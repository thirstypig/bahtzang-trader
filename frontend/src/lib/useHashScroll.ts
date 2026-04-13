"use client";

import { useEffect } from "react";

/**
 * On mount, scrolls to the element matching the current URL hash.
 * Handles the case where Next.js App Router navigates to a page
 * with a hash fragment but the target element renders after mount.
 */
export function useHashScroll() {
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;

    const timeout = setTimeout(() => {
      const el = document.getElementById(hash.slice(1));
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 100);

    return () => clearTimeout(timeout);
  }, []);
}
