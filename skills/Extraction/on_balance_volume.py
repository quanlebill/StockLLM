"""
Retrieve On-Balance Volume (OBV) for a given stock symbol via Alpha Vantage.
OBV tracks cumulative buying/selling pressure using volume and price direction.
Saves raw data to data/raw/{symbol}_on_balance_volume.csv

Usage:
    python on_balance_volume.py --symbol AAPL
    python on_balance_volume.py --symbol AAPL --interval daily
"""

import argparse
import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")


def fetch_obv(symbol: str, interval: str = "daily") -> pd.DataFrame:
    params = {
        "function": "OBV",
        "symbol": symbol,
        "interval": interval,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: OBV"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [{"date": date, "obv": values["OBV"]} for date, values in data[key].items()]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch On-Balance Volume (OBV) from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="daily", choices=["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"])
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching OBV for {symbol}...")
    df = fetch_obv(symbol, args.interval)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_on_balance_volume.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
