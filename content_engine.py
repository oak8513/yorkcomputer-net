"""
content_engine.py — York Computer autonomous SEO content engine.

Pipeline:
  1. Read york-computer-content-gaps.csv (keyword opportunities)
  2. Read content-log.csv (already-published keywords)
  3. Pick highest-opportunity unpublished keyword
  4. Call Claude API (generate_post.py) to write 800-1200 word SEO blog post
  5. Save as _posts/YYYY-MM-DD-{slug}.html (Jekyll auto-lists it)
  6. git commit + push → GitHub Pages auto-deploys
  7. Append result to content-log.csv

Usage:
    python content_engine.py             # normal run
    python content_engine.py --dry-run   # generate post locally, don't push or log
"""
import argparse
import csv
import logging
import sys
from datetime import date
from pathlib import Path

SITE_DIR    = Path(__file__).parent
POSTS_DIR   = SITE_DIR / "_posts"
CONTENT_LOG = SITE_DIR / "content-log.csv"
GAP_CSV     = Path("C:/Users/Owner/Documents/Claude/Projects/content-strategy/output/york-computer-content-gaps.csv")

LOG_FIELDS = ["date", "keyword", "cluster", "slug", "filename", "url", "status", "error"]

CLUSTER_ORDER = [
    "Managed IT Services",
    "Cybersecurity",
    "Small Business IT",
    "Backup & Recovery",
    "Network & Infrastructure",
    "Remote Support",
    "Other",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("content_engine_yc")


def load_published_keywords() -> set:
    if not CONTENT_LOG.exists():
        return set()
    published = set()
    with open(CONTENT_LOG, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "published":
                published.add(row["keyword"].lower().strip())
    return published


def pick_keyword(published: set) -> dict | None:
    if not GAP_CSV.exists():
        log.error("Gap CSV not found: %s", GAP_CSV)
        return None

    rows = []
    with open(GAP_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kw = row["keyword"].lower().strip()
            if kw in published:
                continue
            try:
                vol = int(row.get("avg_monthly_searches") or 0)
            except (ValueError, TypeError):
                vol = 0
            cluster = row.get("cluster", "Other")
            try:
                prio = CLUSTER_ORDER.index(cluster)
            except ValueError:
                prio = len(CLUSTER_ORDER)
            rows.append({**row, "_vol": vol, "_prio": prio})

    if not rows:
        log.info("All keywords in gap CSV have already been published.")
        return None

    rows.sort(key=lambda r: (r["_prio"], -r["_vol"], len(r["keyword"])))
    return rows[0]


def log_result(row: dict) -> None:
    is_new = not CONTENT_LOG.exists()
    with open(CONTENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main(dry_run: bool = False) -> int:
    log.info("=== York Computer Content Engine ===")
    today = date.today().isoformat()

    published = load_published_keywords()
    log.info("Already published: %d keywords", len(published))
    candidate = pick_keyword(published)
    if not candidate:
        log.info("No unpublished keywords remaining — nothing to do.")
        return 0

    keyword = candidate["keyword"]
    cluster = candidate.get("cluster", "Other")
    vol     = candidate.get("avg_monthly_searches", "?")
    log.info("Selected keyword: '%s' (cluster: %s, vol: %s)", keyword, cluster, vol)

    from generate_post import generate_post, render_jekyll_post
    log.info("Calling Claude API to generate post...")
    try:
        post = generate_post(keyword, cluster)
    except Exception as e:
        log.error("Claude API failed: %s", e)
        log_result({"date": today, "keyword": keyword, "cluster": cluster,
                    "slug": "", "filename": "", "url": "", "status": "failed", "error": str(e)})
        return 1

    slug     = post["slug"]
    filename = f"{today}-{slug}.html"
    filepath = POSTS_DIR / filename
    url      = f"https://yorkcomputer.net/blog/{slug}.html"
    log.info("Post slug: %s | File: %s", slug, filename)

    post_html = render_jekyll_post(post, today)

    if dry_run:
        log.info("[DRY RUN] Would write: %s", filepath)
        log.info("[DRY RUN] Post title: %s", post.get("title"))
        return 0

    POSTS_DIR.mkdir(exist_ok=True)
    filepath.write_text(post_html, encoding="utf-8")
    log.info("Saved: %s", filepath)

    from publish_post import git_push
    commit_msg = f"SEO: add post '{post.get('h1', keyword)}' ({today})"
    ok = git_push(commit_msg)
    if not ok:
        log.error("Git push failed — post saved locally but not deployed")
        log_result({"date": today, "keyword": keyword, "cluster": cluster,
                    "slug": slug, "filename": filename, "url": url,
                    "status": "push_failed", "error": "git push returned non-zero"})
        return 1

    log_result({"date": today, "keyword": keyword, "cluster": cluster,
                "slug": slug, "filename": filename, "url": url,
                "status": "published", "error": ""})
    log.info("=== Done — post live at %s ===", url)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="York Computer SEO content engine")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate post locally without saving, pushing, or logging")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
