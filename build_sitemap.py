"""
build_sitemap.py — Regenerates sitemap.xml for yorkcomputer.net from disk.

Walks the site, picks up:
  - /                                (root, from index.html)
  - /services.html, /pricing.html, /about.html, /contact.html
  - /privacy-policy.html, /terms-of-service.html
  - /blog/                           (blog index)
  - /blog/*.html                     (every blog post except index.html)

Excludes: Jekyll source (_posts, _includes, _layouts), assets, internal
legal docs (master-service-agreement.html, service-statement.html).

Run manually:   python build_sitemap.py
Auto-runs from: publish_post.py and the .githooks/pre-commit hook.

Idempotent. Writes Unix line endings + trailing newline to keep diffs clean.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

SITE_DIR = Path(__file__).parent
SITE_URL = "https://yorkcomputer.net"
SITEMAP_PATH = SITE_DIR / "sitemap.xml"

# Top-level pages that should NOT be indexed (legal/internal-only).
EXCLUDE_FILES = {"master-service-agreement.html", "service-statement.html",
                 "404.html"}
EXCLUDE_DIRS = {"_posts", "_includes", "_layouts", "_site", "assets",
                "__pycache__", ".git", "node_modules"}


def _mtime_iso(path: Path) -> str:
    return _dt.date.fromtimestamp(path.stat().st_mtime).isoformat()


def _entry(loc: str, *, lastmod: str | None, changefreq: str, priority: str) -> str:
    parts = [f"  <url>", f"    <loc>{SITE_URL}{loc}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority}</priority>")
    parts.append(f"  </url>")
    return "\n".join(parts)


def collect_urls() -> list[str]:
    entries: list[str] = []

    # 1. Root
    index = SITE_DIR / "index.html"
    if index.exists():
        entries.append(_entry("/", lastmod=_mtime_iso(index),
                              changefreq="weekly", priority="1.0"))

    # 2. Top-level pages with custom priorities
    top_level = [
        ("services.html",         "monthly", "0.9"),
        ("pricing.html",          "monthly", "0.85"),
        ("about.html",            "monthly", "0.7"),
        ("contact.html",          "monthly", "0.8"),
        ("privacy-policy.html",   "yearly",  "0.3"),
        ("terms-of-service.html", "yearly",  "0.3"),
    ]
    for name, freq, prio in top_level:
        p = SITE_DIR / name
        if p.exists():
            entries.append(_entry(f"/{name}", lastmod=_mtime_iso(p),
                                  changefreq=freq, priority=prio))

    # 3. /blog/ index + /blog/*.html
    blog_dir = SITE_DIR / "blog"
    if blog_dir.is_dir():
        blog_index = blog_dir / "index.html"
        if blog_index.exists():
            entries.append(_entry("/blog/", lastmod=_mtime_iso(blog_index),
                                  changefreq="weekly", priority="0.8"))
        for f in sorted(blog_dir.glob("*.html")):
            if f.name == "index.html" or f.name in EXCLUDE_FILES:
                continue
            entries.append(_entry(f"/blog/{f.name}",
                                  lastmod=_mtime_iso(f),
                                  changefreq="monthly", priority="0.9"))

    return entries


def render_sitemap(entries: list[str]) -> str:
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def main() -> int:
    entries = collect_urls()
    new_xml = render_sitemap(entries)

    old_xml = SITEMAP_PATH.read_text(encoding="utf-8") if SITEMAP_PATH.exists() else ""
    if new_xml == old_xml:
        print(f"[build_sitemap] No change — {len(entries)} URLs.")
        return 0

    SITEMAP_PATH.write_text(new_xml, encoding="utf-8", newline="\n")
    print(f"[build_sitemap] Wrote {SITEMAP_PATH.name} with {len(entries)} URLs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
