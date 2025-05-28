#!/usr/bin/env python3
"""
patch-scraper.py – scrape MapleStory patch-note pages (modern layouts only).

• If no URL is given, reads URLs from patch-urls.txt (one per line, # comments ok)
• Outputs grouped JSON into patch-jsons/v###.json
• Includes "__url" field at top of JSON
"""

import argparse, json, re, time, pathlib
from typing import Dict, List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ────────────────────────────────────────  Selenium  ────────────────────────────────────────
def fetch_rendered_html(url: str, timeout: int = 25) -> BeautifulSoup:
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

# ─────────────────────────────────────  Modern parser  ──────────────────────────────────────
def parse_modern_nav(soup: BeautifulSoup) -> Dict[str, List[str]]:
    for ul in soup.find_all("ul"):
        if ul.find("a", href=lambda h: h and h.startswith("#")):
            sections: Dict[str, List[str]] = {}
            current = None
            for el in ul.find_all(["strong", "a"], recursive=True):
                if el.name == "strong":
                    current = el.get_text(strip=True)
                    sections[current] = []
                elif el.name == "a" and current:
                    txt = el.get_text(strip=True)
                    if txt:
                        sections[current].append(txt)
            if sections:
                return sections
    return {}

# ───────────────────────────────────────  Helpers  ──────────────────────────────────────────
def extract_version(soup: BeautifulSoup, url: str) -> str:
    title = soup.title.string if soup.title else ""
    m = re.search(r"\bv[.\-\s]?(\d{3})\b", title, re.I) or re.search(r"\bv[.\-\s]?(\d{3})\b", url, re.I)
    return f"v{m.group(1)}" if m else f"unknown_{int(time.time())}"

def inject_url(nav: Dict[str, List[str]], url: str) -> Dict[str, List[str]]:
    return {"__url": url, **nav}

# ─────────────────────────────────────  Workflow  ───────────────────────────────────────────
def scrape(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        nav = parse_modern_nav(soup)
        if not nav:
            raise RuntimeError("No modern navigation menu found.")
        version = extract_version(soup, url)
        nav = inject_url(nav, url)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{version}.json"
        if out_file.exists() and not overwrite:
            print(f"⚠  {out_file.name} exists – skip (use --overwrite)")
            return
        out_file.write_text(json.dumps(nav, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_file}")
    except Exception as e:
        print(f"✗  {url}  :: {e}")

def load_urls(path: pathlib.Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="Single patch-notes URL")
    ap.add_argument("--url-file", default="patch-urls.txt", help="File with URLs (one per line)")
    ap.add_argument("--out-dir", default="patch-jsons", help="Directory for JSON outputs")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    urls = [args.url] if args.url else load_urls(pathlib.Path(args.url_file))
    if not urls:
        print("No URLs provided and url file is empty.")
        return

    out_dir = pathlib.Path(args.out_dir)
    for u in urls:
        scrape(u, out_dir, args.overwrite)

if __name__ == "__main__":
    main()
