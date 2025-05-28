#!/usr/bin/env python3
"""
patch-scraper.py – scrape MapleStory patch-note pages using the legacy layout (v140 – v165).

• If no URL is given, the script reads from patch-urls-below-v165.txt (one URL per line, “#” comments OK).
• Outputs JSON files into patch-jsons/v###.json – now containing __url and __date at the top.
"""

import argparse, json, re, time, pathlib
from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import OrderedDict

# ───────────────────── Selenium ──────────────────────
def fetch_rendered_html(url: str, timeout: int = 20) -> BeautifulSoup:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    driver.get(url)
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    html = driver.page_source
    driver.quit()
    return BeautifulSoup(html, "lxml")

# ───────────── Legacy section parser ─────────────
EXCLUDE = {"overview", "gameplay", "rewards", "requirement",
           "beginner", "1st job", "2nd job", "3rd job", "4th job",
           "hyper skills"}

def parse_legacy_sections(soup: BeautifulSoup) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    for h1 in soup.find_all("h1"):
        strong = h1.find("strong")
        if not strong:
            continue
        header = strong.get_text(strip=True)
        if header.lower().startswith("check out"):
            continue

        items = []
        for sib in h1.next_siblings:
            if isinstance(sib, Tag) and sib.name == "h1":
                break
            if isinstance(sib, Tag) and sib.name == "h3":
                st = sib.find("strong")
                if not st:
                    continue
                item = st.get_text(strip=True)
                if not item or item.lower() in EXCLUDE:
                    continue
                items.append(item)
        if items:
            sections[header] = items
    return sections

# ─────────────────── Helpers ────────────────────
def extract_version(soup: BeautifulSoup, url: str) -> str:
    m = re.search(r"\bv[.\-\s]?(\d{2,3})\b", url, re.I)
    if not m and soup.title:
        m = re.search(r"\bv[.\-\s]?(\d{2,3})\b", soup.title.get_text(), re.I)
    return f"v{m.group(1)}" if m else f"unknown_{int(time.time())}"

def extract_date(soup: BeautifulSoup) -> str:
    """Return date text from <div class="news-detail__live-date">, e.g. 'Nov 15, 2022'."""
    div = soup.find("div", class_="news-detail__live-date")
    return div.get_text(strip=True) if div else ""

def load_urls(path: pathlib.Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

# ────────────────── Main scraper ──────────────────
def scrape(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        body = parse_legacy_sections(soup)
        if not body:
            raise RuntimeError("No legacy sections found")

        version = extract_version(soup, url)
        date = extract_date(soup)

        # Build JSON with metadata first
        data = OrderedDict()
        data["__url__"]  = url
        data["__date__"] = date
        data.update(body)

        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{version}.json"
        if out_file.exists() and not overwrite:
            print(f"⚠  {out_file.name} exists – skip (use --overwrite)")
            return
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_file}")
    except Exception as e:
        print(f"✗  {url} :: {e}")

# ───────────────────── CLI ──────────────────────
def main():
    ap = argparse.ArgumentParser(description="Scrape legacy MapleStory patch-note pages.")
    ap.add_argument("url", nargs="?", help="Single patch-note URL")
    ap.add_argument("--url-file", default="patch-urls-below-v165.txt", help="File with URLs (one per line)")
    ap.add_argument("--out-dir", default="patch-jsons", help="Directory for JSON outputs")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    urls = [args.url] if args.url else load_urls(pathlib.Path(args.url_file))
    if not urls:
        print("No URLs provided and url-file is empty.")
        return

    out_dir = pathlib.Path(args.out_dir)
    for u in urls:
        scrape(u, out_dir, args.overwrite)

if __name__ == "__main__":
    main()
