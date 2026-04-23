"""
generate_post.py — York Computer blog post generator.

Uses Claude API with prompt caching to write SEO-optimized 800–1200 word
blog posts targeting managed IT / cybersecurity keyword gaps.

Usage:
    python generate_post.py "managed it support small business" "Managed IT Services"
"""
import json
import os
import re
import sys
from datetime import date

import anthropic

SITE_CONTEXT = """You are the content writer for York Computer, a managed IT services and cybersecurity provider in York, Pennsylvania — operating as "Your Digital Bodyguard."

Business facts (use exactly as written):
- Business name: York Computer
- Tagline: Your Digital Bodyguard
- Address: 2069 Carlisle Rd, York, PA 17408
- Phone: 717-739-9675
- Email: help@yorkcomputerrepair.com
- Services: managed IT support, network monitoring, cybersecurity (firewall, antivirus, dark web monitoring), cloud backup & disaster recovery, remote IT support, VoIP phone systems, Microsoft 365 / Google Workspace management, IT consulting for small businesses
- Pricing: flat-rate managed IT starting at $49.99/month per device; free 15-minute security review — no pressure
- Primary audience: small businesses (1–25 employees), home-based businesses, and professionals in York County, PA
- Sister company: York Computer Repair (walk-in hardware repair shop at same address)

Voice & tone:
- Plain English — explain IT concepts like the reader runs a plumbing company, not a tech firm
- Reassuring — "we've got your back, you focus on your business"
- Local York PA angle — mention York, PA, York County, South Central PA, local small businesses
- Practical — give readers one actionable takeaway per article
- Honest — include DIY tips where appropriate; don't oversell
- No filler phrases like "in today's digital landscape" or "it's important to note"

Internal page slugs you may reference naturally in the text:
- Services: /services.html
- Pricing: /pricing.html
- Contact & directions: /contact.html
- About us: /about.html"""


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    secrets = os.path.join(os.path.dirname(__file__), "..", "..", ".secrets", "anthropic.txt")
    if os.path.exists(secrets):
        return open(secrets).read().strip()
    secrets_json = secrets.replace(".txt", ".json")
    if os.path.exists(secrets_json):
        data = json.load(open(secrets_json))
        return data.get("api_key") or data.get("ANTHROPIC_API_KEY", "")
    raise ValueError(
        "ANTHROPIC_API_KEY not found. Set the env var or create "
        "C:\\Users\\Owner\\Documents\\Claude\\.secrets\\anthropic.txt"
    )


def keyword_to_slug(keyword: str) -> str:
    slug = keyword.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:60]


def generate_post(keyword: str, cluster: str) -> dict:
    """Call Claude API and return structured blog post data."""
    client = anthropic.Anthropic(api_key=_get_api_key())

    user_prompt = f"""Write an SEO blog post targeting this keyword: "{keyword}"
Topic cluster: {cluster}

Requirements:
- Total length: 800–1,200 words across all fields combined
- Include "{keyword}" in the title, H1, and at least 2 H2 headings
- Include a York, PA local angle (York County small businesses, local context)
- Reference our services page (/services.html) or pricing page (/pricing.html) naturally at least once
- End with a call to action to call 717-739-9675 or schedule a free 15-minute security review
- Practical and genuinely helpful — not a sales pitch
- No filler phrases like "in today's world" or "it's important to note"

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "title": "Page <title> tag — 50-60 chars, includes keyword",
  "meta_description": "Meta description — 150-160 chars, includes keyword + York PA",
  "slug": "url-friendly-slug",
  "h1": "H1 heading shown to reader",
  "intro": "Opening 2-3 sentence paragraph",
  "sections": [
    {{"h2": "H2 heading", "content": "Body paragraphs as plain text. Separate paragraphs with a blank line."}},
    {{"h2": "H2 heading", "content": "..."}},
    {{"h2": "H2 heading", "content": "..."}}
  ],
  "conclusion": "1-2 sentence closing paragraph",
  "cta_text": "Single CTA sentence (do not include phone/address — those are added by the template)"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=[{"type": "text", "text": SITE_CONTEXT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    if "```" in raw:
        raw = re.sub(r"```[a-z]*\n?", "", raw).replace("```", "").strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import json_repair
            data = json_repair.loads(raw)
        except Exception:
            raw = (raw.replace("\u2018", "'").replace("\u2019", "'")
                      .replace("\u201c", '"').replace("\u201d", '"')
                      .replace("\u2013", "-").replace("\u2014", "-"))
            data = json.loads(raw)

    data["slug"] = keyword_to_slug(data.get("slug") or keyword)
    return data


def render_jekyll_post(data: dict, post_date: str) -> str:
    """Render a Jekyll-compatible HTML file with YAML front matter."""
    slug = data["slug"]
    canonical = f"https://yorkcomputer.net/blog/{slug}.html"
    intro_safe = data.get("intro", "")[:160].replace('"', "")

    front_matter = f"""---
layout: default
title: "{data['title']}"
description: "{data['meta_description']}"
canonical: "{canonical}"
permalink: /blog/{slug}.html
og_type: article
og_title: "{data['title']}"
og_description: "{data['meta_description']}"
date: {post_date}
excerpt: "{intro_safe}"
---"""

    def paras(text: str) -> str:
        return "\n".join(
            f'      <p class="text-yc-steel leading-relaxed mb-5">{p.strip()}</p>'
            for p in text.split("\n\n") if p.strip()
        )

    sections_html = ""
    for sec in data.get("sections", []):
        h2 = sec.get("h2", "")
        sections_html += f'\n      <h2 class="font-heading font-bold text-2xl text-yc-blue mt-10 mb-4">{h2}</h2>\n'
        sections_html += paras(sec.get("content", "")) + "\n"

    cta = data.get("cta_text", "Ready to stop worrying about IT and get back to running your business?")

    body = f"""
<div class="max-w-3xl mx-auto px-4 py-12">

  <!-- Breadcrumb -->
  <nav class="text-sm text-yc-steel mb-6">
    <a href="/" class="hover:text-yc-bright">Home</a>
    <span class="mx-2">&rsaquo;</span>
    <a href="/blog/" class="hover:text-yc-bright">Blog</a>
    <span class="mx-2">&rsaquo;</span>
    <span class="text-yc-black">{data['h1']}</span>
  </nav>

  <!-- Article header -->
  <header class="mb-8">
    <h1 class="font-heading font-bold text-3xl md:text-4xl text-yc-navy leading-tight mb-4">{data['h1']}</h1>
    <div class="flex items-center gap-4 text-sm text-yc-steel">
      <span>York Computer</span>
      <span>&bull;</span>
      <time datetime="{post_date}">{post_date}</time>
      <span>&bull;</span>
      <span>5 min read</span>
    </div>
  </header>

  <!-- Article body -->
  <article class="prose max-w-none">
{paras(data.get('intro', ''))}
{sections_html}
{paras(data.get('conclusion', ''))}
  </article>

  <!-- CTA Box -->
  <div class="mt-10 bg-yc-navy text-white rounded-xl p-8 text-center">
    <p class="font-heading font-semibold text-lg mb-4">{cta}</p>
    <div class="flex flex-col sm:flex-row gap-3 justify-center">
      <a href="tel:7177399675" class="bg-yc-orange hover:bg-orange-700 text-white font-heading font-bold py-3 px-6 rounded-lg transition">Call 717-739-9675</a>
      <a href="/pricing.html" class="border-2 border-white text-white font-heading font-bold py-3 px-6 rounded-lg hover:bg-blue-900 transition">View Plans</a>
    </div>
    <p class="mt-3 text-blue-300 text-sm">Free 15-minute security review &bull; No pressure, no obligation</p>
  </div>

  <!-- Back link -->
  <div class="mt-8 text-center">
    <a href="/blog/" class="text-yc-bright hover:underline font-heading font-semibold text-sm">&larr; Back to all articles</a>
  </div>

</div>"""

    return front_matter + "\n" + body + "\n"


def save_post(data: dict, site_dir: str = None) -> str:
    """Save rendered post to _posts/YYYY-MM-DD-{slug}.html. Returns the file path."""
    if site_dir is None:
        site_dir = os.path.dirname(os.path.abspath(__file__))
    post_date = date.today().isoformat()
    filename = f"{post_date}-{data['slug']}.html"
    posts_dir = os.path.join(site_dir, "_posts")
    os.makedirs(posts_dir, exist_ok=True)
    filepath = os.path.join(posts_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(render_jekyll_post(data, post_date))
    return filepath


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "managed it support small business"
    cl = sys.argv[2] if len(sys.argv) > 2 else "Managed IT Services"
    result = generate_post(kw, cl)
    path = save_post(result)
    print(f"[generate_post] Saved: {path}")
    print(json.dumps(result, indent=2))
