"use client";

import Image from "next/image";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function SidebarProfile({ expanded }: { expanded: boolean }) {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 transition-colors hover:bg-card-alt"
      >
        {user?.picture ? (
          <Image
            src={user.picture}
            alt={user.name || "Profile"}
            width={28}
            height={28}
            className="shrink-0 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-card-alt text-xs font-medium text-secondary">
            {user?.name?.split(" ").filter(Boolean).map((n) => n[0]).join("") || "?"}
          </div>
        )}
        {expanded && (
          <div className="min-w-0 text-left">
            <p className="truncate text-sm font-medium text-primary">{user?.name}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
          </div>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 z-50 mb-2 w-52 rounded-xl border border-border bg-card p-1 shadow-xl">
            <div className="border-b border-border px-3 py-2.5">
              <p className="text-sm font-medium text-primary">{user?.name}</p>
              <p className="text-xs text-muted">{user?.email}</p>
            </div>
            <button
              onClick={() => { setOpen(false); signOut(); }}
              className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-secondary transition-colors hover:bg-card-alt hover:text-primary"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
