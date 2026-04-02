"""
Pull FRED observations for FRED MACRO pipeline target categories:
  CPI/Inflation, Fed Funds Interest Rates, Non-Farm Payroll,
  Consumer Confidence, Yield Curve

Saves one CSV per series_id to data/raw/<series_id_lower>.csv
Columns kept as-is from the FRED API: date, value
"""

import csv
import os
import requests

FRED_API_KEY = "04b2a09fc1ae2346ac1337e92bbf1979"
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

SERIES_IDS = [
    # CPI / Inflation
    "CPI_Headline",
    "Core_CPI",
    "PCE_Headline",
    "Core_PCE",
    "Trimmed_Mean_PCE_YoY",
    "Median_CPI_YoY",
    "PPI_All_Commodities",
    "FedFunds_EffectiveRate_monthly",
    "FedFunds_EffectiveRate_daily",
    "FedFunds_Target_Lower_Limit_daily",
    "FedFunds_Target_Upper_Limit_daily",
    "Total_Nonfarm_Payrolls",
    "1_Month_Treasury_Yield",
    "3_Month_Treasury_Yield",
    "6_Month_Treasury Yield",
    "1_Year_Treasury_Yield",
    "2_Year_Treasury_Yield",
    "5_Year_Treasury_Yield",
    "10_Year_Treasury_Yield",
    "30_Year_Treasury_Yield",
    "10Y_minus_2Y_Spread",
    "10Y_minus_3M_Spread",
]


def pull_series(series_id: str) -> list[dict]:
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("observations", [])


def save_csv(series_id: str, observations: list[dict]) -> None:
    path = os.path.join(OUTPUT_DIR, f"{series_id.lower()}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "date", "value"])
        writer.writeheader()
        for obs in observations:
            writer.writerow({"country": "united states", "date": obs["date"], "value": obs["value"]})
    print(f"  {series_id}: {len(observations)} rows -> {path}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Saving CSVs to: {OUTPUT_DIR}\n")
    for sid in SERIES_IDS:
        try:
            obs = pull_series(sid)
            save_csv(sid, obs)
        except Exception as e:
            print(f"  ERROR {sid}: {e}")
    print("\nDone.")
