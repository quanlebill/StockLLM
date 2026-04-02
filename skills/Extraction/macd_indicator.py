"""
Retrieve MACD (Moving Average Convergence/Divergence) for a given stock symbol via Alpha Vantage.
Default parameters: fast=12, slow=26, signal=9 (standard MACD).
Saves raw data to data/raw/{symbol}_macd_indicator.csv

Usage:
    python macd_indicator.py --symbol AAPL
    python macd_indicator.py --symbol AAPL --fast_period 12 --slow_period 26 --signal_period 9
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


def fetch_macd(symbol: str, interval: str = "daily", series_type: str = "close",
               fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
    params = {
        "function": "MACD",
        "symbol": symbol,
        "interval": interval,
        "series_type": series_type,
        "fastperiod": fast_period,
        "slowperiod": slow_period,
        "signalperiod": signal_period,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: MACD"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [
        {
            "date": date,
            "macd": values["MACD"],
            "macd_signal": values["MACD_Signal"],
            "macd_histogram": values["MACD_Hist"],
        }
        for date, values in data[key].items()
    ]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch MACD technical indicator from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="daily", choices=["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"])
    parser.add_argument("--series_type", default="close", choices=["close", "open", "high", "low"])
    parser.add_argument("--fast_period", type=int, default=12)
    parser.add_argument("--slow_period", type=int, default=26)
    parser.add_argument("--signal_period", type=int, default=9)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching MACD ({args.fast_period}/{args.slow_period}/{args.signal_period}) for {symbol}...")
    df = fetch_macd(symbol, args.interval, args.series_type, args.fast_period, args.slow_period, args.signal_period)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_macd_indicator.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
