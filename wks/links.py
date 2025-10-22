"""
URL organization utilities for WKS.

Parses Markdown files with bare URLs and rewrites them as categorized
Markdown links with readable titles and short blurbs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse, parse_qs, urlunparse


@dataclass
class LinkInfo:
    url: str
    host: str
    path: str
    title: str
    category: str
    blurb: str


_CATEGORY_RULES: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"(^|\.)sciencedirect\.com$", re.I), "Research Papers", "ScienceDirect article"),
    (re.compile(r"(^|\.)inldigitallibrary\.inl\.gov$", re.I), "Research Papers", "INL digital library document"),
    (re.compile(r"(^|\.)inis\.iaea\.org$", re.I), "Research Papers", "IAEA INIS record"),
    (re.compile(r"(^|\.)readthedocs\.io$", re.I), "Docs & Guides", "Documentation"),
    (re.compile(r"(^|\.)docs\.github\.com$", re.I), "Docs & Guides", "GitHub Docs"),
    (re.compile(r"(^|\.)huggingface\.co$", re.I), "AI/ML Tools", "Model/space on Hugging Face"),
    (re.compile(r"(^|\.)ollama\.com$", re.I), "AI/ML Tools", "Ollama model catalog"),
    (re.compile(r"(^|\.)superuser\.com$", re.I), "Q&A / How‑To", "Superuser Q&A"),
    (re.compile(r"(^|\.)microsoftonline\.com$", re.I), "Accounts / Internal", "Microsoft login/OAuth"),
    (re.compile(r"(^|\.)powerbigov\.us$", re.I), "Accounts / Internal", "Power BI Gov"),
    (re.compile(r"(^|\.)localhost$", re.I), "Local / Dev", "Localhost"),
]


def _short_text_from_path(path: str) -> str:
    # Prefer last non-empty path component
    segs = [s for s in path.split('/') if s]
    if not segs:
        return "/"
    last = segs[-1]
    # Strip common GUID-ish or hashy tails
    last = re.sub(r"[?#].*$", "", last)
    last = re.sub(r"%[0-9A-Fa-f]{2}", " ", last)
    # Replace separators with spaces
    disp = re.sub(r"[-_]+", " ", last)
    # Trim very long segments
    return (disp[:60] + "…") if len(disp) > 60 else disp


def _strip_tracking(url: str, host: str) -> str:
    # Keep full URL, but remove obviously useless trackers from common sites
    p = urlparse(url)
    if not p.query:
        return url
    q = parse_qs(p.query, keep_blank_values=True)
    drop_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}
    # For sciencedirect and similar, preserve query (often required), so skip
    if re.search(r"sciencedirect|microsoftonline|powerbi", host, re.I):
        return url
    new_query = "&".join(
        f"{k}={v[0]}" if v else k for k, v in q.items() if k not in drop_keys
    )
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def categorize(url: str) -> LinkInfo:
    p = urlparse(url)
    host = p.hostname or ""
    cleaned = _strip_tracking(url, host)
    # Category/blurb by host rules
    category = "Other"
    blurb = "Link"
    for pat, cat, default_blurb in _CATEGORY_RULES:
        if pat.search(host):
            category = cat
            blurb = default_blurb
            break
    # Derive a readable title
    base = host.replace("www.", "")
    tail = _short_text_from_path(p.path)
    title = base if tail in {"/", ""} else f"{base}: {tail}"
    # Extra heuristics
    if host.endswith("sciencedirect.com") and "/science/article/" in p.path:
        title = f"ScienceDirect article ({p.path.split('/')[-1]})"
    if host.endswith("inis.iaea.org") and "RN:" in cleaned:
        m = re.search(r"RN:(\d+)", cleaned)
        if m:
            title = f"IAEA INIS record RN:{m.group(1)}"
    if cleaned.lower().endswith(".pdf"):
        blurb = "PDF document"
    return LinkInfo(url=cleaned, host=host, path=p.path, title=title, category=category, blurb=blurb)


def extract_urls_from_markdown(text: str) -> List[str]:
    urls: List[str] = []
    # Match http/https URLs in lines; ignore those already formatted as [text](url)
    for line in text.splitlines():
        # Bullets with bare URL
        m = re.findall(r"https?://[^\s)]+", line)
        for u in m:
            urls.append(u.strip())
    return urls


def tidy_markdown_links(md_path: Path) -> str:
    src = md_path.read_text(encoding="utf-8")
    urls = extract_urls_from_markdown(src)
    if not urls:
        return src
    # Dedup while preserving input order
    seen: Dict[str, bool] = {}
    uniq: List[str] = []
    for u in urls:
        if u not in seen:
            uniq.append(u)
            seen[u] = True
    infos = [categorize(u) for u in uniq]
    # Group by category
    by_cat: Dict[str, List[LinkInfo]] = {}
    for info in infos:
        by_cat.setdefault(info.category, []).append(info)
    order = [
        "Research Papers",
        "Docs & Guides",
        "AI/ML Tools",
        "Q&A / How‑To",
        "Accounts / Internal",
        "Local / Dev",
        "Other",
    ]
    # Build output
    lines: List[str] = []
    # Preserve the original top header if present
    header_done = False
    for line in src.splitlines():
        if line.strip().startswith("# ") and not header_done:
            lines.append(line)
            lines.append("")
            header_done = True
            break
    if not header_done:
        lines.append("# Curated Links")
        lines.append("")
    lines.append("Organized by category with short descriptions. Original sources consolidated.")
    lines.append("")
    for cat in order:
        items = by_cat.get(cat) or []
        if not items:
            continue
        lines.append(f"## {cat}")
        for info in items:
            # Markdown link with title; include blurb as dash detail
            lines.append(f"- [{info.title}]({info.url}) — {info.blurb}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_tidy_markdown(md_path: Path) -> Path:
    out = tidy_markdown_links(md_path)
    md_path.write_text(out, encoding="utf-8")
    return md_path

