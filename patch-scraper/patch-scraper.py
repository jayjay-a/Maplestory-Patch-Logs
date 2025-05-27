#!/usr/bin/env python3
"""
batch_patch_scraper.py  –  Scrape MapleStory patch-notes URLs in bulk

Dependencies
------------
pip install selenium beautifulsoup4 lxml

You also need Chrome + matching chromedriver in your PATH.
"""

import re, json, argparse, time, pathlib

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ──────────────────────────────────────────────────────────────────────────────
# Selenium helpers
# ──────────────────────────────────────────────────────────────────────────────
def fetch_rendered_html(url: str, timeout: int = 15) -> BeautifulSoup:
    """Return BeautifulSoup of the fully rendered page."""
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--log-level=3")

    driver = webdriver.Chrome(options=chrome_opts)
    driver.get(url)

    try:
        # Wait until a <ul> containing at least one in-page <a href="#…"> link exists
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//ul[.//a[starts-with(@href, '#')]]"))
        )
    except Exception as e:
        driver.quit()
        raise TimeoutError(f"Timed out waiting for nav block on {url}") from e

    soup = BeautifulSoup(driver.page_source, "lxml")
    driver.quit()
    return soup


# ──────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────────────
def extract_nav_section(soup: BeautifulSoup) -> dict:
    """Return {Section: [items…]} for the first nav <ul>."""
    nav_root = soup.find("ul")
    result, current = {}, None

    for tag in nav_root.find_all(["li", "strong", "a"], recursive=True):
        if tag.name == "strong":
            current = tag.text.strip()
            result[current] = []
        elif tag.name == "a" and current:
            result[current].append(tag.text.strip())
    return result


def extract_patch_version(soup: BeautifulSoup, url: str) -> str | None:
    """Return 'v###' (lower-case) or None if not found."""
    title = soup.title.string if soup.title else ""
    m = re.search(r"\bv[.\-]?\d{2,3}\b", title, re.I) or re.search(r"\bv[\-]?\d{2,3}\b", url, re.I)
    return m.group(0).replace("-", "").replace(".", "").lower() if m else None


# ──────────────────────────────────────────────────────────────────────────────
# Batch runner
# ──────────────────────────────────────────────────────────────────────────────
def scrape_url(url: str, out_dir: pathlib.Path, overwrite: bool):
    try:
        soup = fetch_rendered_html(url)
        nav = extract_nav_section(soup)
        ver = extract_patch_version(soup, url) or f"unknown-{int(time.time())}"
        out_path = out_dir / f"{ver}.json"

        if out_path.exists() and not overwrite:
            print(f"⚠  {out_path.name} exists – skipping (use --overwrite to replace).")
            return

        out_path.write_text(json.dumps(nav, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓  {url}  →  {out_path}")
    except Exception as e:
        print(f"✗  Failed on {url} : {e}")


def load_url_list(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def main():
    p = argparse.ArgumentParser(description="Bulk-scrape MapleStory patch-note URLs.")
    p.add_argument("--url-file", default="patch-urls.txt", help="Text file with URLs (one per line)")
    p.add_argument("--out-dir", default="patch-jsons", help="Directory for JSON outputs")
    p.add_argument("--overwrite", action="store_true", help="Replace existing JSON files")
    args = p.parse_args()

    url_file = pathlib.Path(args.url_file)
    if not url_file.exists():
        raise FileNotFoundError(f"{url_file} not found")

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = load_url_list(url_file)
    if not urls:
        print("No URLs found in", url_file)
        return

    for url in urls:
        scrape_url(url, out_dir, args.overwrite)


if __name__ == "__main__":
    main()
