"use client";

import { useEffect } from "react";

/**
 * Client component that scrolls to the URL hash on mount.
 * Use this in Server Component pages that need hash scroll behavior.
 */
export default function HashScroll() {
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

  return null;
}
