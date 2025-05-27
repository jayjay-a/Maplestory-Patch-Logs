#!/usr/bin/env python3
"""
batch_patch_scraper.py  –  Scrape MapleStory patch-notes URLs in bulk.

Features
--------
1. Modern format: nested <ul> navigation with <strong> section titles.
2. Legacy format: plain-text headings + indented/bulleted sub-items.
3. Auto-detects patch version (v###) for file naming.
4. Batch mode: read URLs from patch-urls.txt, write into patch-jsons/.

Dependencies
------------
pip install selenium beautifulsoup4 lxml
Chrome + matching chromedriver in your PATH.
"""

import re, json, time, argparse, pathlib
from typing import Dict, List

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NavDict = Dict[str, List[str]]


def fetch_rendered_html(url: str, timeout: int = 15) -> BeautifulSoup:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--log-level=3")
    driver = webdriver.Chrome(options=opts)
    driver.get(url)

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.XPATH, "//ul[.//a[starts-with(@href, '#')]]")
            )
        )
    except Exception:
        # Might be legacy format without <ul> nav
        pass

    soup = BeautifulSoup(driver.page_source, "lxml")
    driver.quit()
    return soup


def extract_modern_nav(soup: BeautifulSoup) -> NavDict:
    """Parse the first <ul> containing in-page anchors."""
    for ul in soup.find_all("ul"):
        if ul.find("a", href=lambda h: h and h.startswith("#")):
            sections: NavDict = {}
            current = None
            for el in ul.find_all(["strong", "a"], recursive=True):
                if el.name == "strong":
                    current = el.get_text(strip=True)
                    sections[current] = []
                elif el.name == "a" and current:
                    sections[current].append(el.get_text(strip=True))
            if sections:
                return sections
    return {}


def extract_legacy_nav(soup: BeautifulSoup) -> NavDict:
    """
    Scan for plain-text headings (<h2>, <h3>, <strong> in <p>) and
    group the following <ul> or <p> items under them.
    """
    nav: NavDict = {}
    # Candidate headings: h2, h3, or <strong> inside <p>
    headings = []
    for tag in soup.find_all(["h2", "h3"]):
        headings.append(tag)
    for p in soup.find_all("p"):
        strong = p.find("strong", recursive=False)
        if strong and not strong.find_parent("ul"):
            headings.append(strong)

    # Sort headings in DOM order
    headings.sort(key=lambda t: t.sourceline or 0)

    for heading in headings:
        title = heading.get_text(strip=True)
        if not title:
            continue
        nav[title] = []
        # Collect siblings until next heading
        for sib in heading.parent.next_siblings:
            if isinstance(sib, Tag) and (
                (sib.name in ("h2", "h3")) or sib.find("strong", recursive=False)
            ):
                break
            if isinstance(sib, Tag) and sib.name == "ul":
                for li in sib.find_all("li"):
                    text = li.get_text(strip=True)
                    if text:
                        nav[title].append(text)
            elif isinstance(sib, Tag) and sib.name == "p":
                text = sib.get_text(strip=True)
                if text:
                    nav[title].append(text)
    return nav


def extract_nav_section(soup: BeautifulSoup) -> NavDict:
    """Try modern nav first, then fallback to legacy format."""
    nav = extract_modern_nav(soup)
    if nav:
        return nav
    print("⚠  Using legacy-heading fallback parser")
    return extract_legacy_nav(soup)


def extract_patch_version(soup: BeautifulSoup, url: str) -> str:
    """Normalize 'v###' from title or URL, else timestamp fallback."""
    title = soup.title.string if soup.title else ""
    m = re.search(r"\bv[.\-]?\d{2,3}\b", title, re.I) or re.search(
        r"\bv[\-]?\d{2,3}\b", url, re.I
    )
    if m:
        return m.group(0).replace(".", "").replace("-", "").lower()
    return f"unknown_{int(time.time())}"


def scrape_url(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        nav = extract_nav_section(soup)
        ver = extract_patch_version(soup, url)
        out_path = out_dir / f"{ver}.json"

        if out_path.exists() and not overwrite:
            print(f"⚠  {out_path.name} exists, skipping")
            return

        out_path.write_text(json.dumps(nav, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓  {url} → {out_path.name}")
    except Exception as e:
        print(f"✗  Failed on {url}: {e}")


def load_url_list(path: pathlib.Path) -> List[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def main():
    p = argparse.ArgumentParser(description="Bulk-scrape MapleStory patch-note URLs.")
    p.add_argument("--url-file", default="patch-urls.txt")
    p.add_argument("--out-dir", default="patch-jsons")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()

    url_file = pathlib.Path(args.url_file)
    if not url_file.exists():
        raise FileNotFoundError(f"{url_file} not found")

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)

    urls = load_url_list(url_file)
    if not urls:
        print("No URLs in", url_file)
        return

    for u in urls:
        scrape_url(u, out_dir, args.overwrite)


if __name__ == "__main__":
    main()
