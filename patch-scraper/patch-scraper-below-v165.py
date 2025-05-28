#!/usr/bin/env python3
"""
patch-scraper-legacy.py – scrape legacy MapleStory patch-note pages (old layouts).

• If no URL is given, reads URLs from patch-urls-below-v165.txt (one per line, # comments ok)
• Outputs grouped JSON into patch-jsons/v###.json
"""

import argparse, json, re, time, pathlib
from collections import OrderedDict
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EXCLUDE = {"overview", "gameplay", "rewards", "requirement",
           "beginner", "1st job", "2nd job", "3rd job", "4th job",
           "hyper skills"}

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
        if section.lower().startswith("check out"):   # skip site banner
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

def extract_version(soup: BeautifulSoup, url: str) -> str:
    m = re.search(r"\bv[.\-\s]?(\d{2,3})\b", url, re.I)
    if m:
        return f"v{m.group(1)}"
    title = soup.find("h1")
    if title:
        m = re.search(r"\bv[.\-\s]?(\d{2,3})\b", title.get_text())
        if m:
            return f"v{m.group(1)}"
    return time.strftime("v%Y%m%d%H%M%S")

def extract_date(soup: BeautifulSoup) -> str:
    date_div = soup.select_one("div.news-detail__live-date")
    if date_div:
        return date_div.get_text(strip=True)
    return ""

def scrape(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        data = parse_legacy_sections(soup)
        if not data:
            raise RuntimeError("No legacy sections found")

        version = extract_version(soup, url)
        date = extract_date(soup)
        data["__url__"] = url
        data["__date__"] = date

        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{version}.json"
        if out_file.exists() and not overwrite:
            print(f"⚠  {out_file.name} exists – skip (use --overwrite)")
            return
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_file}")
    except Exception as e:
        print(f"✗  {url}  :: {e}")

def load_urls(path: pathlib.Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

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
