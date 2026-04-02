"""
Retrieve intraday price data including pre-market and after-hours sessions via Alpha Vantage.
Used to capture pre-market / after-hours price movement as a short-term signal.
Saves raw data to data/raw/{symbol}_extended_hours_intraday_price.csv

Usage:
    python extended_hours_intraday_price.py --symbol AAPL
    python extended_hours_intraday_price.py --symbol AAPL --interval 15min --month 2024-01
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


def fetch_extended_hours(symbol: str, interval: str = "15min", month: str = None) -> pd.DataFrame:
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "extended_hours": "true",
        "outputsize": "full",
        "datatype": "json",
        "apikey": API_KEY,
    }
    if month:
        params["month"] = month

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = f"Time Series ({interval})"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = []
    for dt, values in data[key].items():
        records.append({
            "datetime": dt,
            "open": values["1. open"],
            "high": values["2. high"],
            "low": values["3. low"],
            "close": values["4. close"],
            "volume": values["5. volume"],
        })

    df = pd.DataFrame(records).sort_values("datetime").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch intraday price with extended hours from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="15min",
                        choices=["1min", "5min", "15min", "30min", "60min"])
    parser.add_argument("--month", default=None,
                        help="Specific month to retrieve in YYYY-MM format (e.g. 2024-01). Defaults to latest.")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching extended hours intraday price ({args.interval}) for {symbol}...")
    df = fetch_extended_hours(symbol, args.interval, args.month)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_extended_hours_intraday_price.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
