"""
Retrieve upcoming earnings calendar (next 3/6/12 months) via Alpha Vantage.
Used to flag if a stock has an earnings date within the prediction week.
Saves raw data to data/raw/upcoming_earnings_calendar.csv

Usage:
    python upcoming_earnings_calendar.py
    python upcoming_earnings_calendar.py --horizon 3month
    python upcoming_earnings_calendar.py --symbol AAPL
"""

import argparse
import os
import requests
import pandas as pd
from io import StringIO
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


def fetch_earnings_calendar(symbol: str = None, horizon: str = "3month") -> pd.DataFrame:
    params = {
        "function": "EARNINGS_CALENDAR",
        "horizon": horizon,
        "datatype": "csv",
        "apikey": API_KEY,
    }
    if symbol:
        params["symbol"] = symbol

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))
    df = df.sort_values("reportDate").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch upcoming earnings calendar from Alpha Vantage.")
    parser.add_argument("--symbol", default=None,
                        help="Optional: filter by specific stock ticker (e.g. AAPL). Omit for all stocks.")
    parser.add_argument("--horizon", default="3month", choices=["3month", "6month", "12month"],
                        help="Forecast horizon for upcoming earnings")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    symbol_label = args.symbol.upper() if args.symbol else "all"
    print(f"Fetching upcoming earnings calendar (horizon={args.horizon}, symbol={symbol_label})...")
    df = fetch_earnings_calendar(args.symbol, args.horizon)

    output_path = os.path.join(OUTPUT_DIR, f"upcoming_earnings_calendar_{symbol_label}.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
