"use client";

import { useEffect, useState } from "react";
import { getTimezone, setTimezone } from "@/lib/utils";

const TIMEZONES = [
  { value: "America/Los_Angeles", label: "Pacific Time — PT (PST / PDT)" },
  { value: "America/Denver",      label: "Mountain Time — MT (MST / MDT)" },
  { value: "America/Chicago",     label: "Central Time — CT (CST / CDT)" },
  { value: "America/New_York",    label: "Eastern Time — ET (EST / EDT)" },
  { value: "UTC",                  label: "UTC" },
];

export default function SettingsPage() {
  const [tz, setTz] = useState("America/Los_Angeles");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setTz(getTimezone());
  }, []);

  function handleSave() {
    setTimezone(tz);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-primary">Settings</h1>
        <p className="mt-1 text-sm text-muted">
          Display and account preferences
        </p>
      </div>

      <div className="space-y-6">
        {/* Display */}
        <section className="bz-glass rounded-xl p-6">
          <h2 className="mb-1 text-base font-semibold text-primary">Display</h2>
          <p className="mb-5 text-xs text-muted">
            Controls how timestamps appear across the dashboard, trades table, and audit log.
          </p>

          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-primary">
                Timezone
              </label>
              <select
                value={tz}
                onChange={(e) => setTz(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {TIMEZONES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted">
                All trade timestamps are stored in UTC and converted for display. Default: Pacific Time.
              </p>
            </div>
          </div>
        </section>

        {/* Trading defaults — future */}
        <section className="bz-glass-soft rounded-xl p-6 opacity-60">
          <h2 className="mb-1 text-base font-semibold text-primary">Trading Defaults</h2>
          <p className="text-xs text-muted">
            Coming soon — pre-fill values for new portfolio creation (default budget, risk profile).
          </p>
        </section>

        {/* Notifications — future */}
        <section className="bz-glass-soft rounded-xl p-6 opacity-60">
          <h2 className="mb-1 text-base font-semibold text-primary">Notifications</h2>
          <p className="text-xs text-muted">
            Coming soon — Slack webhook for trade execution alerts, daily summary digest.
          </p>
        </section>

        {/* Save */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleSave}
            className="rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Save Settings
          </button>
          {saved && (
            <span className="text-sm text-pos">
              Saved — reload any open page to see updated timestamps.
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
