"""
Retrieve historical earnings data including EPS estimates, actuals, and surprise metrics
for a given stock symbol via Alpha Vantage.
Used to track post-earnings drift signals.
Saves raw data to data/raw/{symbol}_earnings_surprise_history.csv

Usage:
    python earnings_surprise_history.py --symbol AAPL
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


def fetch_earnings_history(symbol: str) -> pd.DataFrame:
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "quarterlyEarnings" not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    df = pd.DataFrame(data["quarterlyEarnings"])
    df = df.sort_values("fiscalDateEnding").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch quarterly earnings history with surprise metrics from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching earnings surprise history for {symbol}...")
    df = fetch_earnings_history(symbol)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_earnings_surprise_history.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
