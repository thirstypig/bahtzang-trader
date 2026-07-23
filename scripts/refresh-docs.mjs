#!/usr/bin/env node
/**
 * refresh-docs.mjs — regenerate the "living" docs from real repo data.
 *
 * Usage:  npm run docs:refresh
 *
 * Writes:
 *   docs/under-the-hood/stats.md          repo shape, doc counts
 *   docs/under-the-hood/costs.md          from docs/costs.config.json
 *   docs/under-the-hood/system-status.md  which service keys are configured
 *   README.md + CLAUDE.md                 status block between DOCS:STATUS markers
 *
 * Everything it writes is DERIVED. Never hand-edit the outputs — change the inputs
 * (the repo, or docs/costs.config.json) and re-run.
 */

import { readFileSync, writeFileSync, existsSync, statSync } from "node:fs";
// execFileSync (not execSync) — no shell is spawned, so nothing can be interpreted
// as a shell metacharacter. These commands take no external input today, but the
// no-shell form keeps it that way if someone later passes a path in.
import { execFileSync } from "node:child_process";
import { dirname, resolve, extname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TODAY = new Date().toISOString().slice(0, 10);
const p = (...s) => resolve(ROOT, ...s);

const TEXT_EXT = new Set([
  ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".md", ".json",
  ".css", ".yml", ".yaml", ".toml", ".sql", ".sh",
]);

// ─────────────────────────────────────────────────────────── helpers

/**
 * Tracked files PLUS untracked-but-not-ignored ones (-c cached, -o others).
 * --exclude-standard applies .gitignore, so this respects ignore rules without
 * parsing them by hand. Including untracked files matters: without -o, anything
 * created but not yet committed is invisible and the stats silently undercount.
 */
function trackedFiles() {
  return execFileSync("git", ["ls-files", "-co", "--exclude-standard"],
    { cwd: ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 })
    .split("\n")
    .filter(Boolean);
}

function readIfExists(abs) {
  try {
    if (!existsSync(abs) || statSync(abs).isDirectory()) return null;
    return readFileSync(abs, "utf8");
  } catch {
    return null;
  }
}

function money(n) {
  return `$${n.toFixed(2)}`;
}

/** Parse a doc's frontmatter. Returns {} when there is none. */
function frontmatter(raw) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(raw);
  if (!m) return {};
  const out = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = /^([a-zA-Z_]+):\s*(.*)$/.exec(line);
    if (kv) out[kv[1]] = kv[2].trim();
  }
  return out;
}

/** Rows of a markdown table whose first cell matches `idRe` and isn't a TODO. */
function tableRows(raw, idRe) {
  if (!raw) return [];
  const rows = [];
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim().startsWith("|")) continue;
    const cells = line.split("|").map((c) => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1);
    if (cells.length < 2) continue;
    if (!idRe.test(cells[0])) continue;
    if (/^TODO$/i.test(cells[1])) continue; // unfilled placeholder row
    rows.push(cells);
  }
  return rows;
}

// ─────────────────────────────────────────────────────────── 6a · stats

function buildStats(files) {
  const byExt = new Map();
  let totalLoc = 0;

  for (const f of files) {
    const ext = extname(f);
    if (!TEXT_EXT.has(ext)) continue;
    const raw = readIfExists(p(f));
    if (raw === null) continue;
    const loc = raw.split("\n").length;
    const e = byExt.get(ext) || { files: 0, loc: 0 };
    e.files += 1;
    e.loc += loc;
    byExt.set(ext, e);
    totalLoc += loc;
  }

  // Routes
  let backendRoutes = 0;
  for (const f of files.filter((f) => f.startsWith("backend/app/") && f.endsWith(".py"))) {
    const raw = readIfExists(p(f)) || "";
    backendRoutes += (raw.match(/@(?:router|app)\.(get|post|put|patch|delete)\s*\(/g) || []).length;
  }
  const frontendPages = files.filter(
    (f) => f.startsWith("frontend/src/app/") && /\/page\.tsx$/.test(f)
  ).length;

  // Docs by type and status (templates excluded)
  const docFiles = files.filter(
    (f) => f.startsWith("docs/") && f.endsWith(".md") && !f.startsWith("docs/_templates/")
  );
  const byType = new Map();
  const byStatus = new Map();
  let noFrontmatter = 0;
  for (const f of docFiles) {
    const fm = frontmatter(readIfExists(p(f)) || "");
    if (!fm.type) { noFrontmatter += 1; continue; }
    byType.set(fm.type, (byType.get(fm.type) || 0) + 1);
    byStatus.set(fm.status || "(none)", (byStatus.get(fm.status || "(none)") || 0) + 1);
  }

  // Roadmap / to-dos
  const roadmap = readIfExists(p("docs/product/roadmap.md"));
  const todos = readIfExists(p("docs/product/todos.md"));
  const rmRows = tableRows(roadmap, /^RM-\d+$/);
  const tdRows = tableRows(todos, /^TD-\d+$/);

  const sortedExt = [...byExt.entries()].sort((a, b) => b[1].loc - a[1].loc);

  const L = [];
  L.push("---", "id: DOC-013", "type: stats", "status: active", "phase: null",
    "owner: james", "tags: [foundations]", "links: [DOC-010]", `updated: ${TODAY}`, "---", "");
  L.push("# Repo stats", "");
  L.push("<!-- GENERATED by scripts/refresh-docs.mjs — do not edit by hand. -->", "");
  L.push("> **Lines of code is a rough vanity signal, tracked for reference only.**",
    "> Real progress is features and phases shipped, not lines written. A refactor that",
    "> deletes 2,000 lines is usually progress, and this number will call it a regression.",
    "");
  L.push(`Generated ${TODAY} from ${files.length} git-tracked files.`, "");

  L.push("## Code", "", "| Type | Files | Lines |", "|---|---:|---:|");
  for (const [ext, e] of sortedExt) L.push(`| \`${ext}\` | ${e.files} | ${e.loc.toLocaleString()} |`);
  L.push(`| **Total** | **${sortedExt.reduce((n, [, e]) => n + e.files, 0)}** | **${totalLoc.toLocaleString()}** |`, "");

  L.push("## Surface area", "", "| Metric | Count |", "|---|---:|");
  L.push(`| Backend routes | ${backendRoutes} |`);
  L.push(`| Frontend pages | ${frontendPages} |`);
  L.push(`| Docs (excluding templates) | ${docFiles.length} |`, "");

  L.push("## Docs by type", "", "| Type | Count |", "|---|---:|");
  for (const [t, n] of [...byType.entries()].sort((a, b) => b[1] - a[1])) L.push(`| ${t} | ${n} |`);
  L.push("");

  L.push("## Docs by status", "", "| Status | Count |", "|---|---:|");
  for (const [s, n] of [...byStatus.entries()].sort((a, b) => b[1] - a[1])) L.push(`| ${s} | ${n} |`);
  L.push("");

  if (noFrontmatter > 0) {
    L.push(`> ⚠ **${noFrontmatter} docs have no frontmatter** and are invisible to the board.`,
      "> Retrofit them or they cannot be found.", "");
  }

  L.push("## Roadmap and to-dos", "");
  if (rmRows.length === 0 && tdRows.length === 0) {
    L.push("_No roadmap items or to-dos defined yet — both tables still hold placeholder rows._", "");
  } else {
    L.push(`**${rmRows.length} roadmap items · ${tdRows.length} to-dos**`, "");
    const shipped = rmRows.filter((r) => /done/i.test(r.join(" ")));
    if (shipped.length) {
      L.push("### Shipped", "");
      for (const r of shipped) L.push(`- \`${r[0]}\` ${r[1]}`);
      L.push("");
    }
  }

  writeFileSync(p("docs/under-the-hood/stats.md"), L.join("\n"), "utf8");
  return { totalLoc, backendRoutes, frontendPages, docCount: docFiles.length, noFrontmatter, rmRows, tdRows };
}

// ─────────────────────────────────────────────────────────── 6b · costs

function buildCosts() {
  const raw = readIfExists(p("docs/costs.config.json"));
  if (!raw) {
    console.warn("⚠ docs/costs.config.json missing — skipping costs.md");
    return null;
  }
  const cfg = JSON.parse(raw);
  const a = cfg.assumptions || {};
  const cyclesPerMonth = (a.tradingDaysPerMonth || 0) * (a.cyclesPerTradingDay || 0);

  const L = [];
  L.push("---", "id: DOC-014", "type: costs", "status: active", "phase: null",
    "owner: james", "tags: [foundations, deployment]", "links: [DOC-013]", `updated: ${TODAY}`, "---", "");
  L.push("# Infrastructure costs", "");
  L.push("<!-- GENERATED by scripts/refresh-docs.mjs from docs/costs.config.json.",
    "     Edit the config, not this file. -->", "");
  L.push("What it costs to run the experiment. **This project has no customers, no plan",
    "price, and no revenue** — so there is no margin model here, deliberately.", "");

  L.push("## Assumptions", "",
    "These drive every number below. If one is wrong, the totals are wrong.", "",
    "| Assumption | Value |", "|---|---:|");
  L.push(`| Trading days per month | ${a.tradingDaysPerMonth ?? "—"} |`);
  L.push(`| Cycles per trading day | ${a.cyclesPerTradingDay ?? "—"} |`);
  L.push(`| Active portfolios | ${a.activePortfolios ?? "—"} |`);
  L.push(`| **Cycles per month** | **${cyclesPerMonth}** |`, "");
  if (a.notes) L.push(`_${a.notes}_`, "");

  const flag = (v) => (v ? " ⚠️ VERIFY" : "");
  let variableTotal = 0, unverified = 0;

  L.push("## Variable costs", "", "| Service | Per unit | Unit | Cycles/mo | Monthly |", "|---|---:|---|---:|---:|");
  for (const c of cfg.variableCosts || []) {
    const monthly = (c.costPerUnitUsd || 0) * cyclesPerMonth;
    variableTotal += monthly;
    if (c.verify) unverified += 1;
    L.push(`| ${c.service}${flag(c.verify)} | ${money(c.costPerUnitUsd || 0)} | ${c.unit || "—"} | ${cyclesPerMonth} | ${money(monthly)} |`);
  }
  L.push(`| **Total variable** | | | | **${money(variableTotal)}** |`, "");

  let fixedTotal = 0;
  L.push("## Fixed costs", "", "| Service | Monthly | Notes |", "|---|---:|---|");
  for (const c of cfg.fixedCosts || []) {
    fixedTotal += c.monthlyUsd || 0;
    if (c.verify) unverified += 1;
    L.push(`| ${c.service}${flag(c.verify)} | ${money(c.monthlyUsd || 0)} | ${c.notes || ""} |`);
  }
  L.push(`| **Total fixed** | **${money(fixedTotal)}** | |`, "");

  L.push("## Total", "", "| | Monthly |", "|---|---:|");
  L.push(`| Variable | ${money(variableTotal)} |`);
  L.push(`| Fixed | ${money(fixedTotal)} |`);
  L.push(`| **Run cost** | **${money(variableTotal + fixedTotal)}** |`, "");

  if (unverified > 0) {
    L.push(`> ⚠️ **${unverified} of ${(cfg.variableCosts || []).length + (cfg.fixedCosts || []).length} figures are unverified.**`,
      "> Every entry marked VERIFY is a placeholder, not a measurement. The total above is",
      "> **not** a real number until they are confirmed against actual invoices.", "");
  }

  writeFileSync(p("docs/under-the-hood/costs.md"), L.join("\n"), "utf8");
  return { variableTotal, fixedTotal, unverified };
}

// ─────────────────────────────────────────────────────────── 6c · status

function buildStatus() {
  // Key NAMES come from .env.example; we report presence only, never values.
  const example = readIfExists(p("backend/.env.example")) || "";
  const keys = [...new Set((example.match(/^[A-Z][A-Z0-9_]*/gm) || []))].sort();
  const envRaw = readIfExists(p("backend/.env")) || "";
  const configured = new Set();
  for (const line of envRaw.split(/\r?\n/)) {
    const m = /^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/.exec(line.trim());
    if (m && m[2].replace(/["']/g, "").trim() !== "") configured.add(m[1]);
  }

  let lastCommit = "unknown";
  try {
    lastCommit = execFileSync("git", ["log", "-1", "--format=%cd", "--date=short"],
      { cwd: ROOT, encoding: "utf8" }).trim();
  } catch { /* not a git repo */ }

  const L = [];
  L.push("---", "id: DOC-015", "type: status", "status: active", "phase: null",
    "owner: james", "tags: [deployment, backend]", "links: [DOC-007]", `updated: ${TODAY}`, "---", "");
  L.push("# System status", "");
  L.push("<!-- GENERATED by scripts/refresh-docs.mjs — do not edit by hand. -->", "");
  L.push("> **Configuration check only — this is not a health check.**",
    "> A key being present means it exists in the local `backend/.env`. It does not mean",
    "> the service is reachable, the key is valid, or the quota is intact. The 13-day",
    "> silent outage in June had every key configured the whole time.", "");
  L.push(`Last commit: **${lastCommit}**`, "");
  L.push("<!-- TODO: deploy timestamp requires the Railway API; commit date is a proxy. -->", "");

  const known = keys.filter((k) => configured.has(k));
  const undocumented = [...configured].filter((k) => !keys.includes(k)).sort();

  L.push("## Service keys", "", "| Key | Local config |", "|---|---|");
  for (const k of keys) L.push(`| \`${k}\` | ${configured.has(k) ? "configured" : "— absent"} |`);
  L.push("");
  L.push("_Values are never read or printed — presence only._", "");
  L.push(`_${known.length} of ${keys.length} documented keys configured locally. Production values live in Railway and are not visible here._`, "");

  if (undocumented.length) {
    L.push("");
    L.push(`> ⚠ **${undocumented.length} key(s) set in \`backend/.env\` but missing from \`.env.example\`:**`);
    L.push(`> ${undocumented.map((k) => `\`${k}\``).join(", ")}`);
    L.push("> A new contributor copying `.env.example` would not know these are needed.");
  }

  L.push("");
  L.push("<!-- FUTURE: real health checks. Dormant until there is something depending on");
  L.push("     uptime. Shape to fill in then:");
  L.push("");
  L.push("     | Service   | Ping | Latency | Uptime 30d | Last error |");
  L.push("     |-----------|------|---------|------------|------------|");
  L.push("     | Alpaca    | ok   | 120ms   | 99.9%      | —          |");
  L.push("     | Supabase  | ok   | 40ms    | 100%       | —          |");
  L.push("     | Anthropic | ok   | 2.1s    | 99.7%      | 404 model  |");
  L.push("");
  L.push("     Implement by pinging each service's cheapest endpoint and recording the");
  L.push("     result. Do NOT build this before it is needed — an unread dashboard that");
  L.push("     makes real API calls on a schedule is pure cost. -->");

  writeFileSync(p("docs/under-the-hood/system-status.md"), L.join("\n"), "utf8");
  return { keys: keys.length, configured: known.length, undocumented: undocumented.length };
}

// ─────────────────────────────────────────────────────────── 6d · snippets

const START = "<!-- DOCS:STATUS:START -->";
const END = "<!-- DOCS:STATUS:END -->";

function snippet(stats) {
  const L = [];
  L.push(START);
  L.push(`<!-- Generated by npm run docs:refresh on ${TODAY}. Do not edit by hand. -->`);
  L.push("");
  L.push("### Project status");
  L.push("");
  const phase = stats.rmRows.length ? "see roadmap" : "not set in roadmap.md";
  L.push(`**Current phase:** ${phase}`);
  L.push("");
  L.push("**Next 3 to-dos:**");
  L.push("");
  if (stats.tdRows.length === 0) {
    L.push("_None defined yet — `docs/product/todos.md` still holds placeholder rows._");
  } else {
    for (const r of stats.tdRows.slice(0, 3)) L.push(`- \`${r[0]}\` ${r[1]}`);
  }
  L.push("");
  L.push("Full roadmap: [`docs/product/roadmap.md`](docs/product/roadmap.md)");
  L.push("");
  L.push(END);
  return L.join("\n");
}

function updateSnippet(file, block) {
  const abs = p(file);
  const raw = readIfExists(abs);
  if (raw === null) return `${file}: not found`;
  if (!raw.includes(START) || !raw.includes(END)) {
    return `${file}: markers missing — add ${START} / ${END} where you want the block`;
  }
  const re = new RegExp(`${START}[\\s\\S]*?${END}`);
  writeFileSync(abs, raw.replace(re, block), "utf8");
  return `${file}: updated`;
}

// ─────────────────────────────────────────────────────────── main

const files = trackedFiles();
const stats = buildStats(files);
const costs = buildCosts();
const status = buildStatus();
const block = snippet(stats);
const snippetResults = [updateSnippet("README.md", block), updateSnippet("CLAUDE.md", block)];

console.log(`✓ stats.md          ${stats.totalLoc.toLocaleString()} LOC · ${stats.backendRoutes} routes · ${stats.frontendPages} pages · ${stats.docCount} docs`);
if (stats.noFrontmatter) console.log(`  ⚠ ${stats.noFrontmatter} docs without frontmatter (invisible to the board)`);
if (costs) console.log(`✓ costs.md          ${money(costs.variableTotal + costs.fixedTotal)}/mo · ⚠ ${costs.unverified} figures unverified`);
console.log(`✓ system-status.md  ${status.configured}/${status.keys} documented keys configured locally`);
if (status.undocumented) console.log(`  ⚠ ${status.undocumented} key(s) in .env missing from .env.example`);
for (const r of snippetResults) console.log(`  ${r}`);
