"""
Scrape GDP statistics for all countries from Worldometer.
Saves raw data to data/raw/worldometer_gdp_by_country.csv

Columns: rank, country, gdp_nominal_usd, gdp_full_value_usd, gdp_growth_pct, gdp_per_capita_usd

Usage:
    python worldometer_gdp_by_country.py
"""

import os
import csv
import re
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
URL = "https://www.worldometers.info/gdp/gdp-by-country/"


def clean(text: str) -> str:
    return text.strip()


def parse_gdp_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("No table found on page")

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 6:
            continue
        rows.append({
            "rank":               clean(cells[0]),
            "country":            clean(cells[1]),
            "gdp_nominal_usd":    clean(cells[2]),
            "gdp_full_value_usd": clean(cells[3]),
            "gdp_growth_pct":     clean(cells[4]),
            "gdp_per_capita_usd": clean(cells[5]),
        })
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching GDP by country from Worldometer...")
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    rows = parse_gdp_table(response.text)

    output_path = os.path.join(OUTPUT_DIR, "worldometer_gdp_by_country.csv")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "country", "gdp_nominal_usd", "gdp_full_value_usd", "gdp_growth_pct", "gdp_per_capita_usd"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
