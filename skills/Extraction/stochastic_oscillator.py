"""
Retrieve Stochastic Oscillator (%K and %D) for a given stock symbol via Alpha Vantage.
Saves raw data to data/raw/{symbol}_stochastic_oscillator.csv

Usage:
    python stochastic_oscillator.py --symbol AAPL
    python stochastic_oscillator.py --symbol AAPL --fastkperiod 5 --slowkperiod 3 --slowdperiod 3
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


def fetch_stochastic_oscillator(symbol: str, interval: str = "daily",
                                 fastkperiod: int = 5, slowkperiod: int = 3,
                                 slowdperiod: int = 3) -> pd.DataFrame:
    params = {
        "function": "STOCH",
        "symbol": symbol,
        "interval": interval,
        "fastkperiod": fastkperiod,
        "slowkperiod": slowkperiod,
        "slowdperiod": slowdperiod,
        "datatype": "json",
        "apikey": API_KEY,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    key = "Technical Analysis: STOCH"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = [
        {
            "date": date,
            "slow_k": values["SlowK"],
            "slow_d": values["SlowD"],
        }
        for date, values in data[key].items()
    ]
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch Stochastic Oscillator (%K, %D) from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--interval", default="daily", choices=["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"])
    parser.add_argument("--fastkperiod", type=int, default=5)
    parser.add_argument("--slowkperiod", type=int, default=3)
    parser.add_argument("--slowdperiod", type=int, default=3)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching Stochastic Oscillator for {symbol}...")
    df = fetch_stochastic_oscillator(symbol, args.interval, args.fastkperiod, args.slowkperiod, args.slowdperiod)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_stochastic_oscillator.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
