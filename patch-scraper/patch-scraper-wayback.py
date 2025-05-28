#!/usr/bin/env python3
"""
patch-scraper-wayback.py — Scrape MapleStory patch notes from Wayback URLs.

• Supports single URL or batch via patch-urls-wayback.txt
• Extracts:
  - __url__
  - __date__   (e.g. Jun 19, 2013)
  - __title__  (e.g. Unleashed)
  - Patch section TOC items
• Outputs JSON to patch-jsons/vXXX.json
"""

import argparse, json, re, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import requests
from bs4 import BeautifulSoup, Tag

# ───────────────────── fetch + utilities ─────────────────────
def fetch(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def version_from(url: str, soup: BeautifulSoup) -> str:
    m = re.search(r"\bv[.\-\s]?(\d{3})\b", url, re.I) \
        or (soup.title and re.search(r"\bv[.\-\s]?(\d{3})\b", soup.title.get_text(), re.I))
    return f"v{m.group(1)}" if m else f"unknown_{int(time.time())}"

def title_from(soup: BeautifulSoup) -> str:
    hdr = soup.find("div", id="m-news-detail-header")
    if hdr:
        h4 = hdr.find("h4")
        if h4:
            title = h4.get_text(strip=True)
            title = re.sub(r"^v[.\-\s]?\d+\s*-\s*", "", title, flags=re.I)
            title = re.sub(r"\s*Update Notes$", "", title, flags=re.I)
            return title.strip()
    return "Untitled"

def date_from(soup: BeautifulSoup, url: str) -> str:
    hdr = soup.find("div", id="m-news-detail-header")
    if hdr:
        info = hdr.find("div", class_="info")
        if info:
            m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", info.get_text())
            if m:
                dt = datetime.strptime(m.group(1), "%m/%d/%Y")
                return dt.strftime("%b %d, %Y")
    # fallback to Wayback timestamp
    m = re.search(r"/web/(\d{14})/", url)
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").strftime("%b %d, %Y") if m else "Unknown"

# ───────────────────── TOC scraper ─────────────────────
def parse_wayback_toc(soup: BeautifulSoup) -> Dict[str, List[str]]:
    toc_start = soup.find("h1", string=re.compile("Table of Contents", re.I))
    if not toc_start:
        raise RuntimeError("Couldn't find <h1>Table of Contents</h1>")

    result: Dict[str, List[str]] = {}
    current_section = None
    node = toc_start

    while node := node.find_next_sibling():
        if isinstance(node, Tag):
            if node.name == "h1":
                break  # end of TOC
            elif node.name == "b":
                current_section = node.get_text(strip=True)
                if current_section:
                    result[current_section] = []
            elif node.name == "ul" and current_section:
                for li in node.find_all("li"):
                    a = li.find("a")
                    if a:
                        text = a.get_text(strip=True)
                        if text:
                            result[current_section].append(text)

    return {k: v for k, v in result.items() if v}

# ───────────────────── scrape & write ─────────────────────
def scrape(url: str, out_dir: Path, overwrite: bool):
    soup = fetch(url)
    toc = parse_wayback_toc(soup)
    if not toc:
        raise RuntimeError("No TOC sections found")

    data = {
        "__url__": url,
        "__date__": date_from(soup, url),
        "__title__": title_from(soup),
        **toc
    }

    version = version_from(url, soup)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{version}.json"
    if out_file.exists() and not overwrite:
        print(f"⚠  {out_file.name} exists – skipping (use --overwrite)")
        return

    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓  {url} → {out_file}")

# ───────────────────── CLI + batch ─────────────────────
def load_urls(path: Path) -> List[str]:
    return [
        ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="Single Wayback patch URL (optional)")
    ap.add_argument("--url-file", default="patch-urls-wayback.txt", help="URL list (default: patch-urls-wayback.txt)")
    ap.add_argument("--out-dir", default="patch-jsons", help="Output directory")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON")
    args = ap.parse_args()

    urls = [args.url] if args.url else load_urls(Path(args.url_file))
    if not urls:
        print("No URLs provided.")
        return

    for u in urls:
        try:
            scrape(u, Path(args.out_dir), args.overwrite)
        except Exception as e:
            print(f"✗  {u} :: {e}")

if __name__ == "__main__":
    main()
