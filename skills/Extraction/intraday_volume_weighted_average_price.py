"""
Retrieve intraday VWAP (Volume Weighted Average Price) for a given stock symbol via Alpha Vantage.
VWAP is only available at intraday intervals.
Saves raw data to data/raw/{symbol}_intraday_vwap.csv

Usage:
    python intraday_volume_weighted_average_price.py --symbol AAPL
    python intraday_volume_weighted_average_price.py --symbol AAPL --interval 15min
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


def fetch_vwap(symbol: str, interval: str = "15min") -> pd.DataFrame:
    params = {
        "function": "VWAP",
        "symbol": symbol,
        "interval": interval,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: VWAP"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [{"datetime": dt, "vwap": values["VWAP"]} for dt, values in data[key].items()]
    df = pd.DataFrame(records).sort_values("datetime").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch intraday VWAP from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="15min",
                        choices=["1min", "5min", "15min", "30min", "60min"],
                        help="Intraday interval (VWAP is intraday only)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching intraday VWAP ({args.interval}) for {symbol}...")
    df = fetch_vwap(symbol, args.interval)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_intraday_vwap.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
