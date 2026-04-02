"""
Retrieve insider transactions (Form 4 filings) for a given stock symbol via Alpha Vantage.
Captures buy/sell activity by founders, executives, and board members.
Saves raw data to data/raw/{symbol}_insider_transactions.csv

Usage:
    python insider_transactions.py --symbol AAPL
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


def fetch_insider_transactions(symbol: str) -> pd.DataFrame:
    params = {
        "function": "INSIDER_TRANSACTIONS",
        "symbol": symbol,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "data" not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    df = pd.DataFrame(data["data"])
    if "transaction_date" in df.columns:
        df = df.sort_values("transaction_date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch insider transactions (Form 4) from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching insider transactions for {symbol}...")
    df = fetch_insider_transactions(symbol)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_insider_transactions.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
