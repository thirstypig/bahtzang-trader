// Minimal markdown → HTML for the /docs admin board. Docs are our own repo files,
// not user input, so this is a formatter, not a sanitizer (links are still guarded).

const FRONTMATTER = /^---\n[\s\S]*?\n---\n/;
const TABLE_ROW = /^\|.*\|\s*$/;
const TABLE_SEPARATOR = /^\|[\s:|-]+\|\s*$/;

function splitRow(line: string): string[] {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
}

// Collapse each markdown table into a single line of HTML so the line-based
// rules below (headers, lists, paragraphs) leave it alone.
function renderTables(md: string): string {
  const lines = md.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (TABLE_ROW.test(lines[i]) && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1])) {
      const header = splitRow(lines[i]);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      const th = header
        .map((c) => `<th class="border-b border-border px-3 py-2 text-left font-semibold text-primary">${c}</th>`)
        .join("");
      const tr = rows
        .map((r) => `<tr>${r.map((c) => `<td class="border-b border-border px-3 py-2 align-top text-secondary">${c}</td>`).join("")}</tr>`)
        .join("");
      out.push(`<div class="my-4 overflow-x-auto"><table class="w-full text-xs"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`);
      continue;
    }
    out.push(lines[i]);
    i++;
  }
  return out.join("\n");
}

export function renderMarkdown(md: string): string {
  let html = renderTables(md.replace(FRONTMATTER, ""))
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="rounded-lg bg-card-alt p-4 overflow-x-auto text-xs font-mono text-secondary my-3"><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="rounded bg-card-alt px-1.5 py-0.5 text-xs font-mono text-accent">$1</code>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="mt-6 mb-2 text-base font-semibold text-primary">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="mt-8 mb-3 text-lg font-bold text-primary border-b border-border pb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="mt-8 mb-4 text-xl font-bold text-primary">$1</h1>')
    // Bold and italic
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-primary">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Links — strip javascript: URIs before injecting into href
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
      const safe = /^(https?:\/\/|\/|#)/.test(url) ? url : "#";
      return `<a href="${safe}" target="_blank" rel="noopener noreferrer" class="text-accent underline hover:text-accent-text">${text}</a>`;
    })
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-secondary">$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal text-secondary">$1</li>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr class="my-6 border-border" />')
    // Paragraphs (lines not already wrapped)
    .replace(/^(?!<[hluop]|<li|<hr|<pre|<code|<div)(.+)$/gm, '<p class="my-2 text-secondary leading-relaxed">$1</p>');

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li[^>]*>.*<\/li>\n?)+)/g, '<ul class="my-3 space-y-1">$1</ul>');

  return html;
}
