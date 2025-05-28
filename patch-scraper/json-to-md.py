#!/usr/bin/env python3
import json
import pathlib
import re
from typing import Dict, List, Optional

PATCH_DIR = pathlib.Path("patch-jsons")
OUTPUT_FILE = pathlib.Path("../README.md")

def extract_version_num(version: str) -> int:
    # Extract digits from version string like 'v259' → 259
    m = re.search(r"\d+", version)
    return int(m.group()) if m else 0

def format_patch_summary(version: str, date: Optional[str], url: Optional[str], sections: Dict[str, List[str]]) -> str:
    date_part = f" ({date})" if date else ""
    summary = f"{version}{date_part}"
    md = [f"<details>\n  <summary>\n    {summary}\n  </summary>"]
    if url:
        md.append(f"\n  URL: {url}\n")
    for section, items in sections.items():
        if section.startswith("__"):  # skip metadata keys like __url__, __date__
            continue
        for item in items:
            md.append(f"  - {section}: {item}")
    md.append("</details>\n")
    return "\n".join(md)

def load_patches(dir_path: pathlib.Path) -> List[Dict]:
    patches = []
    for file in dir_path.glob("*.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            url = data.get("__url__", None)
            date = data.get("__date__", None)  # Use as-is, no parsing
            # Remove metadata keys to get only sections
            sections = {k: v for k, v in data.items() if not k.startswith("__")}
            version = file.stem
            patches.append({
                "version": version,
                "date": date,
                "url": url,
                "sections": sections
            })
        except Exception as e:
            print(f"Warning: failed to load {file}: {e}")
    return patches

def main():
    patches = load_patches(PATCH_DIR)
    # Sort descending by version number
    patches.sort(key=lambda p: extract_version_num(p["version"]), reverse=True)

    md_blocks = [format_patch_summary(p["version"], p["date"], p["url"], p["sections"]) for p in patches]

    new_content = "\n".join(md_blocks) + "\n"

    if OUTPUT_FILE.exists():
        old_text = OUTPUT_FILE.read_text(encoding="utf-8")
    else:
        old_text = ""

    # Insert new_content at the top, separated by two newlines
    combined = new_content + "\n\n" + old_text

    OUTPUT_FILE.write_text(combined, encoding="utf-8")
    print(f"Wrote combined markdown for {len(patches)} patches to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
