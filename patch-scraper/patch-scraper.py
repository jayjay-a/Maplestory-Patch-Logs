#!/usr/bin/env python3
"""
this should work for 261 with new
patch-scraper.py – scrape MapleStory patch-note pages (modern layout).

• If no URL is given, reads URLs from patch-urls.txt.
• Outputs JSON into patch-jsons/v###.json with __url__, __date__, __title__.
"""

import argparse, json, re, time, pathlib
from typing import Dict, List
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ───────────────────── HTML fetch ─────────────────────
def fetch_rendered_html(url: str, timeout: int = 30) -> BeautifulSoup:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    driver.get(url)

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(5)
    except Exception:
        print("⚠ Timeout: <body> did not appear in time.")
        html = driver.page_source
        driver.quit()
        return BeautifulSoup(html, "lxml")

    html = driver.page_source
    driver.quit()
    return BeautifulSoup(html, "lxml")


# ───────────────────── navigation UL ───────────────────
def parse_modern_nav(soup: BeautifulSoup) -> dict:
    # Find the top-level TOC <ul> (assuming you already have the right <ul>)
    ul = soup.find("ul")
    if not ul:
        return {}

    sections = {}

    for li in ul.find_all("li", recursive=False):
        # Section title is inside span > strong
        span = li.find("span", recursive=False)
        if span:
            strong = span.find("strong", recursive=False)
            if strong:
                section_title = strong.get_text(strip=True)
                sections[section_title] = []

                # The nested <ul> with the actual links/items
                nested_ul = li.find("ul", recursive=False)
                if nested_ul:
                    # Parse nested <li> items recursively
                    sections[section_title] = parse_nav_items(nested_ul)
    return sections


def parse_nav_items(ul_tag):
    """
    Recursively parse <ul> of TOC items into list.
    Each <li> can be:
    - a link (string)
    - or a nested dict if contains nested ul
    """
    items = []
    for li in ul_tag.find_all("li", recursive=False):
        a = li.find("a", recursive=False)
        nested_ul = li.find("ul", recursive=False)

        if a and nested_ul:
            # This <li> has a link and nested sub-items, nest them as dict
            key = a.get_text(strip=True)
            items.append({key: parse_nav_items(nested_ul)})
        elif a:
            # Just a link item
            items.append(a.get_text(strip=True))
        elif nested_ul:
            # No link but has nested items — parse them and extend
            items.extend(parse_nav_items(nested_ul))
        else:
            # Fallback: text only li (rare)
            text = li.get_text(strip=True)
            if text:
                items.append(text)
    return items



# ───────────────────── metadata helpers ────────────────
VERSION_RE = re.compile(r"\bv[.\-\s]?(\d{3})\b", re.I)

def extract_version(soup: BeautifulSoup, url: str) -> str:
    m = VERSION_RE.search(url)
    if not m and soup.title:
        m = VERSION_RE.search(soup.title.get_text())
    return f"v{m.group(1)}" if m else f"unknown_{int(time.time())}"

def extract_date(soup: BeautifulSoup) -> str:
    div = soup.select_one(".news-detail__live-date")
    if div:
        return div.get_text(strip=True)
    # fallback: nothing
    return ""

def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("h1.news-detail__title") or soup.find("h1")
    if not h1:
        return ""
    raw = h1.get_text(strip=True)

    # Remove [Updated …]
    raw = re.sub(r"^\s*\[.*?\]\s*", "", raw)
    # Remove version prefix with optional hyphen/dash
    raw = re.sub(r"^\s*[Vv][.\s]?\d{1,3}\s*[-–]?\s*", "", raw)
    # Remove trailing words like "Patch Notes" or "Update Highlights"
    raw = re.sub(r"\s*(Patch\s*Notes|Update\s*Highlights)\s*$", "", raw, flags=re.I)
    return raw.strip(" –-")


# ───────────────────── page parser ─────────────────────
def parse_page(soup: BeautifulSoup) -> Dict[str, List[str]]:
    content = soup.select_one(".fr-view") or soup.select_one(".news-detail__content") or soup
    return parse_modern_nav(content) or {}


# ───────────────────── main scrape ─────────────────────
def scrape(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        body = parse_page(soup)
        version = extract_version(soup, url)
        date = extract_date(soup)
        title = extract_title(soup)

        # metadata first
        data = {"__url__": url, "__date__": date, "__title__": title, **body}

        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{version}.json"
        if out_file.exists() and not overwrite:
            print(f"⚠  {out_file.name} exists – skip (use --overwrite)")
            return
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_file}")
    except Exception as e:
        print(f"✗  {url}  :: {e}")

# ───────────────────── CLI ────────────────────────
def load_urls(path: pathlib.Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="Single patch-note URL")
    ap.add_argument("--url-file", default="patch-urls.txt")
    ap.add_argument("--out-dir", default="patch-jsons")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    urls = [args.url] if args.url else load_urls(pathlib.Path(args.url_file))
    if not urls:
        print("No URLs provided.")
        return

    out_dir = pathlib.Path(args.out_dir)
    for u in urls:
        scrape(u, out_dir, args.overwrite)

if __name__ == "__main__":
    main()
