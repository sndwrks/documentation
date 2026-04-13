#!/usr/bin/env python3
"""Generate public/llms.txt from documentation source files using the Anthropic API."""

import glob
import os
import re
import sys
from pathlib import Path

import anthropic


def load_dotenv():
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


DOCS_ROOT = Path("src/content/docs")
OUTPUT_PATH = Path("public/llms.txt")
EXCLUDED_FILES = {"reference/z_doc-style.mdx"}

SIDEBAR_SECTIONS = ["Products", "Guides", "Reference"]


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract title and description from YAML frontmatter using regex."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fm_block = match.group(1)
    result = {}
    for key in ("title", "description"):
        m = re.search(rf"^{key}:\s*(.+)$", fm_block, re.MULTILINE)
        if m:
            result[key] = m.group(1).strip().strip("'\"")
    return result


def file_to_url_path(filepath: Path) -> str:
    """Convert a docs file path to its URL path (relative, no leading slash)."""
    rel = filepath.relative_to(DOCS_ROOT)
    # Strip extension
    without_ext = rel.with_suffix("")
    url = str(without_ext).replace(os.sep, "/")
    # index files map to the directory root
    if url == "index" or url.endswith("/index"):
        url = url.removesuffix("index").rstrip("/")
    return url


def classify_section(url_path: str) -> str | None:
    """Return the sidebar section name for a URL path."""
    for section in SIDEBAR_SECTIONS:
        if url_path.startswith(section.lower()):
            return section
    return None


def discover_docs() -> list[dict]:
    """Find all doc files with their metadata and content."""
    docs = []
    for pattern in ("**/*.md", "**/*.mdx"):
        for filepath in DOCS_ROOT.glob(pattern):
            rel = filepath.relative_to(DOCS_ROOT)
            rel_str = str(rel).replace(os.sep, "/")

            if rel_str in EXCLUDED_FILES:
                continue

            content = filepath.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            url_path = file_to_url_path(filepath)
            section = classify_section(url_path)

            docs.append(
                {
                    "filepath": rel_str,
                    "url_path": url_path,
                    "title": fm.get("title", rel.stem),
                    "description": fm.get("description", ""),
                    "section": section,
                    "content": content,
                }
            )
    return docs


def build_prompt(docs: list[dict], site_url: str) -> str:
    """Build the user prompt with llms.txt spec rules, site info, and doc contents."""
    docs_listing = ""
    for doc in docs:
        docs_listing += (
            f"\n### File: {doc['filepath']}\n"
            f"- Title: {doc['title']}\n"
            f"- Description: {doc['description']}\n"
            f"- URL path: /{doc['url_path']}\n"
            f"- Sidebar section: {doc['section'] or 'Top-level'}\n"
            f"\n<content>\n{doc['content']}\n</content>\n"
        )

    return f"""Generate an llms.txt file for the following documentation site.

## llms.txt spec rules (from llmstxt.org)

- Start with an H1 containing the project/site name
- A blockquote providing a short summary of the project
- Any additional information in paragraphs (optional)
- H2 sections grouping related links
- Each link as a Markdown list item: `- [Title](url): description`
- Links must be absolute URLs
- The file should be concise and informative for LLMs to understand the site

## Site information

- Site name: sndwrks
- Base URL: {site_url}
- Sidebar sections (use these as H2 headings): {', '.join(SIDEBAR_SECTIONS)}

## Documentation files

{docs_listing}

## Instructions

- Output ONLY the raw llms.txt Markdown content, no code fences or explanation
- Use the base URL to construct absolute URLs for each page
- Group links under H2 headings matching the sidebar sections: {', '.join(SIDEBAR_SECTIONS)}
- The root/index page should be listed before the sections, not inside one
- Write concise but informative descriptions based on the actual page content
- Do not include the excluded internal style guide page"""


def main():
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    site_url = os.environ.get("SITE_URL", "").rstrip("/")
    if not site_url:
        print("Error: SITE_URL environment variable is required.", file=sys.stderr)
        sys.exit(1)

    docs = discover_docs()
    if not docs:
        print("Error: No documentation files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(docs)} documentation files.")

    client = anthropic.Anthropic(api_key=api_key)

    print("Calling Anthropic API to generate llms.txt...")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0,
        system="You generate llms.txt files following the llmstxt.org specification. Output raw Markdown only, no code fences or surrounding explanation.",
        messages=[{"role": "user", "content": build_prompt(docs, site_url)}],
    )

    llms_txt = message.content[0].text

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(llms_txt + "\n", encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
