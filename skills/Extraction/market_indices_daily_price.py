"""
Retrieve daily price data for key market indices: SPY (S&P 500), QQQ (NASDAQ), VIX.
Used to measure broad market trend and fear/volatility context over the past 5 days.
Saves raw data to data/raw/market_indices_daily_price.csv

Usage:
    python market_indices_daily_price.py
    python market_indices_daily_price.py --symbols SPY QQQ VIX --outputsize full
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

DEFAULT_SYMBOLS = ["SPY", "QQQ", "VIX"]


def fetch_daily_price(symbol: str, outputsize: str = "compact") -> pd.DataFrame:
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "Time Series (Daily)" not in data:
        raise ValueError(f"Unexpected response for {symbol}: {data.get('Note') or data.get('Information') or data}")

    records = []
    for date, values in data["Time Series (Daily)"].items():
        records.append({
            "date": date,
            "symbol": symbol,
            "open": values["1. open"],
            "high": values["2. high"],
            "low": values["3. low"],
            "close": values["4. close"],
            "volume": values["5. volume"],
        })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Fetch daily price data for market indices from Alpha Vantage.")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help="List of symbols to retrieve (default: SPY QQQ VIX)")
    parser.add_argument("--outputsize", default="compact", choices=["compact", "full"])
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_frames = []
    for symbol in args.symbols:
        symbol = symbol.upper()
        print(f"Fetching daily price for {symbol}...")
        df = fetch_daily_price(symbol, args.outputsize)
        all_frames.append(df)

    combined = pd.concat(all_frames).sort_values(["date", "symbol"]).reset_index(drop=True)

    output_path = os.path.join(OUTPUT_DIR, "market_indices_daily_price.csv")
    combined.to_csv(output_path, index=False)
    print(f"Saved {len(combined)} rows to {output_path}")


if __name__ == "__main__":
    main()
