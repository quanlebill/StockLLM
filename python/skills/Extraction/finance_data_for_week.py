import yfinance as yf
import sys
import os
import re
from pathlib import Path

Sectors = {
    'XLK': 'Technology',
    'XLF' :'Financials'	,
    'XLV':'Health Care'	,
    'XLY': 'Consumer Discretionary',
    'XLP':'Consumer Staples',
    'XLE': 'Energy'	,
    'XLI': 'Industrials'	,
    'XLB': 'Materials',
    'XLU' :'Utilities'	,
    'XLRE':'Real Estate',
    'XLC':'Communication Services',
}

Importances = {
    '^TYX': 'Yield Spread',
    '^VIX': 'Fear Index',
    '^GSPC': 'S&P 500',
}
__DIR__ = Path(os.environ["STOCKLLM_ROOT"], "data")
if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else None
    if ticker is None:
        assert False, f"No ticker provided."

    if not re.search("^--ticker=", ticker):
        assert False, f"Invalid ticker argument provided. must be --ticker=your_ticker."

    ticker = ticker.replace("--ticker=", "")


    try:
        stock = yf.download(ticker, period="2y").reset_index()
        stock.to_csv(__DIR__ / "raw" / f"{ticker.replace("^","").lower()}.csv", index=False)
        stock_info = yf.Ticker(ticker).info.get('sector')
        for sector_symbol, sector_name in Sectors.items():
            if sector_name == stock_info:
                sector_data = yf.download(sector_symbol, period="2y").reset_index()
                sector_data.to_csv(__DIR__ / "raw" / f"sector_{sector_symbol}_{sector_name.replace(" ", "_").lower()}.csv", index=False)
                break
    except Exception as e:
        print(f"Fail to download data for {ticker}")
        print(e)

    for data_symbol, data_name in Importances.items():
        try:
            data = yf.download(data_symbol, period="2y").reset_index()
            data.to_csv(__DIR__ / "raw" /f"{data_name.replace(" ", "_").lower()}.csv", index=False)
        except Exception as e:
            print(f"Fail to download data for {data_name}")

