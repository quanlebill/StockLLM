"""
Retrieve historical options chain data for a given stock symbol via Alpha Vantage.
Includes implied volatility (IV), Greeks (delta, gamma, theta, vega), open interest, and volume.
Used to derive: put/call ratio, IV vs RV comparison, gamma exposure by strike.
Saves raw data to data/raw/{symbol}_historical_options_{date}.csv

Usage:
    python historical_options_chain.py --symbol AAPL
    python historical_options_chain.py --symbol AAPL --date 2024-01-19
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


def fetch_historical_options(symbol: str, date: str = None) -> pd.DataFrame:
    params = {
        "function": "HISTORICAL_OPTIONS",
        "symbol": symbol,
        "datatype": "json",
        "apikey": API_KEY,
    }
    if date:
        params["date"] = date

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "data" not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    df = pd.DataFrame(data["data"])
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch historical options chain from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--date", default=None,
                        help="Specific date in YYYY-MM-DD format. Defaults to most recent trading day.")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching historical options chain for {symbol} (date={args.date or 'latest'})...")
    df = fetch_historical_options(symbol, args.date)

    date_label = args.date if args.date else "latest"
    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_historical_options_{date_label}.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
