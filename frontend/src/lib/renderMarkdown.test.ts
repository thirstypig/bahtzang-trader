import { describe, it, expect } from "vitest";
import { renderMarkdown } from "./renderMarkdown";

describe("renderMarkdown", () => {
  it("strips YAML frontmatter", () => {
    const html = renderMarkdown("---\nid: DOC-053\ntype: guide\n---\n\n# Title\n");
    expect(html).not.toContain("DOC-053");
    expect(html).toContain("<h1");
  });

  it("renders a markdown table with header and body cells", () => {
    const md = "| Feature | Live? |\n|---|---|\n| Stop-loss | **No** |\n| Kill switch | `Yes` |\n";
    const html = renderMarkdown(md);
    expect(html).toContain("<table");
    expect(html.match(/<th /g)).toHaveLength(2);
    expect(html.match(/<tr>/g)).toHaveLength(3);
    expect(html).toContain("<strong");
    expect(html).toContain("<code");
    expect(html).not.toContain("<p class=\"my-2 text-secondary leading-relaxed\">|");
  });

  it("leaves a lone pipe line without a separator as a paragraph", () => {
    expect(renderMarkdown("| not a table |")).toContain("<p");
  });

  it("renders numbered lists as list items", () => {
    expect(renderMarkdown("1. First\n2. Second").match(/<li/g)).toHaveLength(2);
  });

  it("still neutralises javascript: links", () => {
    expect(renderMarkdown("[x](javascript:alert(1))")).toContain('href="#"');
  });
});
