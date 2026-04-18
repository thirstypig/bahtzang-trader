"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { concepts, Concept } from "@/data/concepts";
import HashScroll from "@/components/HashScroll";
import CrossLink from "@/components/CrossLink";

const TABS = [
  { key: "strategic", label: "Strategic" },
  { key: "seo", label: "SEO Pages" },
  { key: "integrations", label: "Integrations" },
  { key: "ux", label: "UX Mockups" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  exploring: { bg: "bg-amber-900/30", text: "text-amber-400" },
  planned: { bg: "bg-blue-900/30", text: "text-blue-400" },
  building: { bg: "bg-purple-900/30", text: "text-purple-400" },
  shipped: { bg: "bg-emerald-900/30", text: "text-emerald-400" },
};

function useTabs(defaultTab: TabKey = "strategic") {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const raw = searchParams.get("tab");
  const activeTab: TabKey = TABS.some((t) => t.key === raw) ? (raw as TabKey) : defaultTab;

  function setTab(tab: TabKey) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return [activeTab, setTab] as const;
}

export default function ConceptsPage() {
  const [activeTab, setTab] = useTabs();

  const tabConcepts = concepts.filter((c) => c.tab === activeTab);

  const tabCounts = TABS.reduce(
    (acc, tab) => {
      acc[tab.key] = concepts.filter((c) => c.tab === tab.key).length;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <HashScroll />
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-primary">Concepts</h1>
        <p className="mt-1 text-sm text-muted">
          Ideas and explorations — {concepts.length} concepts across {TABS.length} categories
        </p>
      </div>

      {/* Tab bar */}
      <div
        role="tablist"
        aria-label="Concept categories"
        className="flex border-b border-border"
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            id={`tab-${tab.key}`}
            aria-selected={activeTab === tab.key}
            aria-controls={`panel-${tab.key}`}
            onClick={() => setTab(tab.key)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.key ? "text-primary" : "text-muted hover:text-secondary"
            }`}
          >
            {tab.label}
            <span className="ml-1.5 text-[10px] text-muted">{tabCounts[tab.key]}</span>
            {activeTab === tab.key && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />
            )}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      {TABS.map((tab) => (
        <div
          key={tab.key}
          role="tabpanel"
          id={`panel-${tab.key}`}
          aria-labelledby={`tab-${tab.key}`}
          hidden={activeTab !== tab.key}
          tabIndex={0}
          className="mt-6 focus:outline-none"
        >
          {activeTab === tab.key && (
            <div className="space-y-4">
              {tabConcepts.map((concept) => (
                <ConceptCard key={concept.id} concept={concept} />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ConceptCard({ concept }: { concept: Concept }) {
  const statusStyle = STATUS_STYLES[concept.status] || STATUS_STYLES.exploring;

  return (
    <div
      id={concept.id}
      className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-border-strong"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-primary">{concept.title}</h3>
        <span
          className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${statusStyle.bg} ${statusStyle.text}`}
        >
          {concept.status}
        </span>
      </div>

      <p className="mt-2 text-sm leading-relaxed text-secondary">{concept.description}</p>

      {concept.phases && (
        <ol className="mt-3 space-y-1">
          {concept.phases.map((phase, i) => (
            <li key={i} className="flex gap-2 text-xs text-muted">
              <span className="shrink-0 font-mono text-muted">{i + 1}.</span>
              {phase}
            </li>
          ))}
        </ol>
      )}

      {concept.details && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(concept.details).map(([key, value]) => (
            <div key={key} className="text-xs">
              <span className="text-muted">{key}:</span>{" "}
              <span className="text-secondary">{value}</span>
            </div>
          ))}
        </div>
      )}

      {concept.roadmapSection && (
        <div className="mt-3 flex items-center gap-2 border-t border-border/50 pt-3">
          <span className="text-[10px] text-muted">Related:</span>
          <CrossLink type="roadmap" href={concept.roadmapSection} />
        </div>
      )}
    </div>
  );
}
