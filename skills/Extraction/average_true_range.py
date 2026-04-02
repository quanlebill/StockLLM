"""
Retrieve Average True Range (ATR) for a given stock symbol via Alpha Vantage.
ATR is a volatility proxy measuring average price range over a given period.
Saves raw data to data/raw/{symbol}_average_true_range.csv

Usage:
    python average_true_range.py --symbol AAPL
    python average_true_range.py --symbol AAPL --time_period 14
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


def fetch_atr(symbol: str, interval: str = "daily", time_period: int = 14) -> pd.DataFrame:
    params = {
        "function": "ATR",
        "symbol": symbol,
        "interval": interval,
        "time_period": time_period,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: ATR"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [{"date": date, "atr": values["ATR"]} for date, values in data[key].items()]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch Average True Range (ATR) from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="daily", choices=["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"])
    parser.add_argument("--time_period", type=int, default=14)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching ATR ({args.time_period}-period) for {symbol}...")
    df = fetch_atr(symbol, args.interval, args.time_period)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_average_true_range.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
