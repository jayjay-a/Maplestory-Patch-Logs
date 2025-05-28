#!/usr/bin/env python3
"""
patch-scraper.py – scrape MapleStory patch-note pages using legacy layout (v140–v200).

• If no URL is given, reads from patch-urls-below-v165.txt (one per line, # comments ok)
• Outputs grouped JSON into patch-jsons/v###.json
"""

import argparse, json, re, time, pathlib
from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ────────────────────────────── Selenium ──────────────────────────────
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

# ────────────────────────────── Legacy parser ──────────────────────────────
EXCLUDE = {"overview", "gameplay", "rewards", "requirement",
           "beginner", "1st job", "2nd job", "3rd job", "4th job",
           "hyper skills"}

def parse_legacy_sections(soup: BeautifulSoup) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    headers = soup.find_all("h1")
    for h1 in headers:
        strong = h1.find("strong")
        if not strong:
            continue
        section = strong.get_text(strip=True)
        if section.lower().startswith("check out"):
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
            result[section] = items
    return result

# ────────────────────────────── Helpers ──────────────────────────────
def extract_version(soup: BeautifulSoup, url: str) -> str:
    title = soup.title.string if soup.title else ""
    m = re.search(r"\bv[.\-\s]?(\d{3})\b", title, re.I) or re.search(r"\bv[.\-\s]?(\d{3})\b", url, re.I)
    return f"v{m.group(1)}" if m else f"unknown_{int(time.time())}"

def load_urls(path: pathlib.Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

# ────────────────────────────── Main ──────────────────────────────
def scrape(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        data = parse_legacy_sections(soup)
        if not data:
            raise RuntimeError("No legacy sections found.")

        version = extract_version(soup, url)
        out_file = out_dir / f"{version}.json"
        if out_file.exists() and not overwrite:
            print(f"⚠  {out_file.name} exists – skip (use --overwrite)")
            return

        data_with_meta = {"__url": url, **data}
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(data_with_meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_file}")

    except Exception as e:
        print(f"✗  {url}  :: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="Single patch-notes URL")
    ap.add_argument("--url-file", default="patch-urls-below-v165.txt", help="File with URLs (one per line)")
    ap.add_argument("--out-dir", default="patch-jsons", help="Directory for JSON outputs")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = ap.parse_args()

    if args.url:
        urls = [args.url]
    else:
        url_file = pathlib.Path(args.url_file)
        if not url_file.exists():
            print("No URL arg and patch-urls-below-v165.txt not found.")
            return
        urls = load_urls(url_file)

    out_dir = pathlib.Path(args.out_dir)
    for u in urls:
        scrape(u, out_dir, args.overwrite)

if __name__ == "__main__":
    main()
