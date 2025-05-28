#!/usr/bin/env python3
"""
Download MapleStory patch-notes navigation (v140–v163 only)

usage:
  python patch-scraper-below-v165.py [url ...]
  python patch-scraper-below-v165.py                # loads from patch-urls-below-v165.txt
"""

import argparse, json, os, re, sys, time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def chrome_driver(headless: bool = True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--log-level=3")
    return webdriver.Chrome(options=opts)

def wait_for_body(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(("tag name", "body"))
    )

def fetch_html(url: str) -> BeautifulSoup:
    driver = chrome_driver()
    print(f"Loading {url} ...")
    driver.get(url)
    wait_for_body(driver)
    html = driver.page_source
    driver.quit()
    return BeautifulSoup(html, "html.parser")

# ───── legacy (≤v163) parser ─────
EXCLUDE = {"overview", "gameplay", "rewards", "requirement",
           "beginner", "1st job", "2nd job", "3rd job", "4th job",
           "hyper skills"}

def parse_legacy_sections(soup: BeautifulSoup) -> Optional[Dict[str, List[str]]]:
    result: Dict[str, List[str]] = OrderedDict()
    headers = soup.find_all("h1")
    if not headers:
        return None

    for h1 in headers:
        strong = h1.find("strong")
        if not strong:
            continue
        section = strong.get_text(strip=True)
        if section.lower().startswith("check out"):
            continue

        result[section] = []
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
                result[section].append(item)

    return {k: v for k, v in result.items() if v} or None

PATCH_RE = re.compile(r"[vV][\.\-]?(\d{2,3})")

def patch_version(url: str, soup: BeautifulSoup) -> str:
    # 1) Look in URL
    m = PATCH_RE.search(url)
    if m:
        return f"v{m.group(1)}"

    # 2) Try <h1> text
    h1 = soup.find("h1")
    if h1:
        m = PATCH_RE.search(h1.get_text(" ", strip=True))
        if m:
            return f"v{m.group(1)}"

        # 3) Try inside <strong> within <h1>
        strong = h1.find("strong")
        if strong:
            m = PATCH_RE.search(strong.get_text(" ", strip=True))
            if m:
                return f"v{m.group(1)}"

    # fallback to timestamp if version not found
    print("⚠️  Could not find patch version — using timestamp.")
    return time.strftime("v%Y%m%d%H%M%S")


def scrape_url(url: str, out_dir: Path) -> bool:
    soup = fetch_html(url)
    nav = parse_legacy_sections(soup)
    if not nav:
        raise RuntimeError("Unable to extract navigation tree.")

    version = patch_version(url, soup)
    out_file = out_dir / f"{version}.json"
    out_file.write_text(json.dumps(nav, indent=2, ensure_ascii=False))
    print(f"✓  {url}  →  {out_file}")
    return True

def load_url_list(txtfile: Path) -> List[str]:
    if not txtfile.exists():
        return []
    return [
        line.strip()
        for line in txtfile.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main():
    parser = argparse.ArgumentParser(description="Scrape legacy MapleStory patch-note navigation.")
    parser.add_argument("urls", nargs="*", help="Patch-note URLs")
    parser.add_argument("--url-file", default="patch-urls-below-v165.txt")
    parser.add_argument("--out-dir", default="patch-jsons")
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    urls = args.urls or load_url_list(Path(args.url_file))
    if not urls:
        parser.error("No URLs provided and url-file is empty.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    for u in urls:
        try:
            scrape_url(u, out_dir)
            ok += 1
        except Exception as exc:
            print(f"✗  Failed on {u} : {exc.__class__.__name__}: {exc}")

    print(f"\nFinished: {ok}/{len(urls)} successful.")

if __name__ == "__main__":
    main()
