"""
Retrieve news sentiment data for a given stock symbol via Alpha Vantage.
Covers sentiment scores from premier news outlets over the past 1-3 days.
Saves raw data to data/raw/{symbol}_news_sentiment.csv

Usage:
    python news_sentiment.py --symbol AAPL
    python news_sentiment.py --symbol AAPL --time_from 20240101T0000 --limit 50
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


def fetch_news_sentiment(symbol: str, time_from: str = None, time_to: str = None,
                         limit: int = 50) -> pd.DataFrame:
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "limit": limit,
        "datatype": "json",
        "apikey": API_KEY,
    }
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if "feed" not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    records = []
    for article in data["feed"]:
        # Extract ticker-specific sentiment score for the requested symbol
        ticker_sentiment = next(
            (t for t in article.get("ticker_sentiment", []) if t["ticker"] == symbol),
            {}
        )
        records.append({
            "time_published": article.get("time_published"),
            "title": article.get("title"),
            "source": article.get("source"),
            "overall_sentiment_score": article.get("overall_sentiment_score"),
            "overall_sentiment_label": article.get("overall_sentiment_label"),
            "ticker_relevance_score": ticker_sentiment.get("relevance_score"),
            "ticker_sentiment_score": ticker_sentiment.get("ticker_sentiment_score"),
            "ticker_sentiment_label": ticker_sentiment.get("ticker_sentiment_label"),
            "url": article.get("url"),
        })

    df = pd.DataFrame(records).sort_values("time_published").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch news sentiment data from Alpha Vantage.")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--time_from", default=None,
                        help="Start time in YYYYMMDDTHHMM format (e.g. 20240101T0000)")
    parser.add_argument("--time_to", default=None,
                        help="End time in YYYYMMDDTHHMM format")
    parser.add_argument("--limit", type=int, default=50, help="Max number of articles (max 1000)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching news sentiment for {symbol}...")
    df = fetch_news_sentiment(symbol, args.time_from, args.time_to, args.limit)

    output_path = os.path.join(OUTPUT_DIR, f"{symbol}_news_sentiment.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
