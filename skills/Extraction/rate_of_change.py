"""
Retrieve Rate of Change (ROC) for a given stock symbol via Alpha Vantage.
Supports 5-day and 10-day ROC for short-term price momentum.
Saves raw data to data/raw/{symbol}_rate_of_change_{period}day.csv

Usage:
    python rate_of_change.py --symbol AAPL
    python rate_of_change.py --symbol AAPL --time_period 5
    python rate_of_change.py --symbol AAPL --time_period 10
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


def fetch_roc(symbol: str, interval: str = "daily", time_period: int = 10,
              series_type: str = "close") -> pd.DataFrame:
    params = {
        "function": "ROC",
        "symbol": symbol,
        "interval": interval,
        "time_period": time_period,
        "series_type": series_type,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: ROC"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [{"date": date, "roc": values["ROC"]} for date, values in data[key].items()]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch Rate of Change (ROC) from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="daily", choices=["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"])
    parser.add_argument("--time_period", type=int, default=10, help="ROC lookback period in days (e.g. 5 or 10)")
    parser.add_argument("--series_type", default="close", choices=["close", "open", "high", "low"])
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching ROC ({args.time_period}-day) for {symbol}...")
    df = fetch_roc(symbol, args.interval, args.time_period, args.series_type)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_rate_of_change_{args.time_period}day.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
