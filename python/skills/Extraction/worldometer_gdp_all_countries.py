"""
Scrape GDP Nominal, PPP, and World Bank data for all countries from Worldometer.
Each country has its own page with historical yearly tables.
Saves last 4 years only to:
  - data/raw/worldometer_gdp_nominal.csv
  - data/raw/worldometer_gdp_ppp.csv
  - data/raw/worldometer_gdp_world_bank.csv

Usage:
    python worldometer_gdp_all_countries.py
"""

import os
import csv
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.worldometers.info"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
HEADERS = {"User-Agent": "Mozilla/5.0"}
YEARS_TO_KEEP = 4
DELAY_SECONDS = 0.5


def clean_number(value: str) -> str:
    """Strip currency symbols, commas, percent signs — return plain number string."""
    return value.strip().lstrip("$").replace(",", "").rstrip("%").strip()


def get_country_links() -> list[tuple[str, str]]:
    """Return list of (country_name, url_path) from main GDP page."""
    r = requests.get(f"{BASE_URL}/gdp/", headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # country pages follow /gdp/{slug}-gdp/ pattern
        if href.startswith("/gdp/") and href.endswith("-gdp/") and href != "/gdp/":
            name = a.get_text(strip=True)
            if name:
                links.append((name, href))
    # deduplicate by href
    seen = set()
    unique = []
    for name, href in links:
        if href not in seen:
            seen.add(href)
            unique.append((name, href))
    return unique


def parse_country_gdp(country_name: str, url_path: str) -> dict:
    """
    Fetch a country GDP page and return dict with keys:
      nominal: list of row dicts
      ppp:     list of row dicts
      wb:      list of row dicts
    Each row has: country, year, + relevant columns
    """
    url = f"{BASE_URL}{url_path}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 3:
        return None

    current_year = 2026
    cutoff_year = current_year - YEARS_TO_KEEP  # keep years > cutoff

    def parse_table(table, row_builder):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            try:
                year = int(cells[0])
            except (ValueError, IndexError):
                continue
            if year <= cutoff_year:
                continue
            row = row_builder(country_name, year, cells)
            if row:
                rows.append(row)
        return rows

    # Table 0 — Nominal GDP (IMF)
    nominal = parse_table(tables[0], lambda c, y, cells: {
        "country":            c,
        "year":               y,
        "gdp_nominal_usd":    clean_number(cells[1]) if len(cells) > 1 else "",
        "gdp_growth_pct":     clean_number(cells[2]) if len(cells) > 2 else "",
        "gdp_per_capita_usd": clean_number(cells[3]) if len(cells) > 3 else "",
    })

    # Table 1 — PPP GDP (IMF)
    ppp = parse_table(tables[1], lambda c, y, cells: {
        "country":                c,
        "year":                   y,
        "gdp_ppp_usd":            clean_number(cells[1]) if len(cells) > 1 else "",
        "gdp_ppp_per_capita_usd": clean_number(cells[2]) if len(cells) > 2 else "",
    })

    # Table 2 — World Bank GDP
    wb = parse_table(tables[2], lambda c, y, cells: {
        "country":          c,
        "year":             y,
        "gdp_nominal_usd":  clean_number(cells[1]) if len(cells) > 1 else "",
        "gdp_real_usd":     clean_number(cells[2]) if len(cells) > 2 else "",
    })

    return {"nominal": nominal, "ppp": ppp, "wb": wb}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching country list...")
    country_links = get_country_links()
    print(f"Found {len(country_links)} countries\n")

    all_nominal, all_ppp, all_wb = [], [], []
    failed = []

    for i, (name, path) in enumerate(country_links):
        print(f"[{i+1}/{len(country_links)}] {name} ({path})", end=" ... ")
        try:
            result = parse_country_gdp(name, path)
            if result:
                all_nominal.extend(result["nominal"])
                all_ppp.extend(result["ppp"])
                all_wb.extend(result["wb"])
                print(f"nominal={len(result['nominal'])} ppp={len(result['ppp'])} wb={len(result['wb'])}")
            else:
                print("skipped (no tables)")
                failed.append(path)
        except Exception as e:
            print(f"ERROR: {e}")
            failed.append(path)
        time.sleep(DELAY_SECONDS)

    # Save nominal
    nominal_path = os.path.join(OUTPUT_DIR, "worldometer_gdp_nominal.csv")
    with open(nominal_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "year", "gdp_nominal_usd", "gdp_growth_pct", "gdp_per_capita_usd"])
        writer.writeheader()
        writer.writerows(all_nominal)
    print(f"\nSaved {len(all_nominal)} rows -> {nominal_path}")

    # Save PPP
    ppp_path = os.path.join(OUTPUT_DIR, "worldometer_gdp_ppp.csv")
    with open(ppp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "year", "gdp_ppp_usd", "gdp_ppp_per_capita_usd"])
        writer.writeheader()
        writer.writerows(all_ppp)
    print(f"Saved {len(all_ppp)} rows -> {ppp_path}")

    # Save World Bank
    wb_path = os.path.join(OUTPUT_DIR, "worldometer_gdp_world_bank.csv")
    with open(wb_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "year", "gdp_nominal_usd", "gdp_real_usd"])
        writer.writeheader()
        writer.writerows(all_wb)
    print(f"Saved {len(all_wb)} rows -> {wb_path}")

    if failed:
        print(f"\nFailed ({len(failed)}): {failed}")


if __name__ == "__main__":
    main()
