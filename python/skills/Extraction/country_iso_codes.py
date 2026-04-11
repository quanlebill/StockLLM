"""
Generate a country reference list with country_name, iso_alpha_2_code, iso_alpha_3_code
using the pycountry library.
Saves to data/raw/country_iso_codes.csv

Usage:
    python country_iso_codes.py
"""

import os
import csv
import pycountry

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    rows = []
    for country in pycountry.countries:
        rows.append({
            "country_name":    country.name,
            "iso_alpha_2_code": country.alpha_2,
            "iso_alpha_3_code": country.alpha_3,
        })

    rows.sort(key=lambda r: r["country_name"])

    output_path = os.path.join(OUTPUT_DIR, "country_iso_codes.csv")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country_name", "iso_alpha_2_code", "iso_alpha_3_code"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} countries to {output_path}")


if __name__ == "__main__":
    main()
