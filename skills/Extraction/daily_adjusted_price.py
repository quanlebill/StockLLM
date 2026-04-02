"""
Retrieve daily adjusted OHLCV price data for a given stock symbol via Alpha Vantage.
Saves raw data to data/raw/{symbol}_daily_adjusted_price.csv

Usage:
    python daily_adjusted_price.py --symbol AAPL
    python daily_adjusted_price.py --symbol AAPL --outputsize full
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


def fetch_daily_adjusted_price(symbol: str, outputsize: str = "compact") -> pd.DataFrame:
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": outputsize,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "Time Series (Daily)" not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = []
    for date, values in data["Time Series (Daily)"].items():
        records.append({
            "date": date,
            "open": values["1. open"],
            "high": values["2. high"],
            "low": values["3. low"],
            "close": values["4. close"],
            "adjusted_close": values["5. adjusted close"],
            "volume": values["6. volume"],
            "dividend_amount": values["7. dividend amount"],
            "split_coefficient": values["8. split coefficient"],
        })

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch daily adjusted OHLCV price data from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--outputsize", default="compact", choices=["compact", "full"],
                        help="compact = last 100 data points, full = 20+ years of history")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching daily adjusted price for {symbol}...")
    df = fetch_daily_adjusted_price(symbol, args.outputsize)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_daily_adjusted_price.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
