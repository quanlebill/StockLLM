"""
market_scan.py — Batch-analyse a curated universe of large-cap tickers
and return ranked buy candidates.

Public API
----------
scan(top_n=10, period="1y") -> dict
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from skills.yfinance.stock_analysis import analyze

# ── Universe — top ~50 S&P 500 components by market cap ─────────────────────
UNIVERSE: list[str] = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO",
    "ORCL", "NFLX", "CSCO", "QCOM", "TXN", "INTU", "CRM", "IBM", "AMD",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "AMGN", "PFE",
    # Financials
    "JPM", "V", "MA", "BAC", "GS", "MS", "BRK-B", "SPGI",
    # Consumer
    "COST", "HD", "PG", "KO", "WMT", "MCD", "PEP", "NKE",
    # Energy
    "XOM", "CVX",
    # Industrials
    "GE", "CAT", "HON", "RTX",
    # Telecom / other
    "T", "VZ", "ACN", "PM",
]

_VERDICT_RANK = {
    "STRONG BUY": 0,
    "BUY": 1,
    "HOLD": 2,
    "SELL": 3,
    "STRONG SELL": 4,
}


def _safe_analyze(ticker: str, period: str) -> dict:
    try:
        result = analyze(ticker, period)
        result["_ok"] = "error" not in result
        return result
    except Exception as exc:
        return {"ticker": ticker, "_ok": False, "error": str(exc)}


def scan(top_n: int = 10, period: str = "1y", workers: int = 10) -> dict:
    """
    Analyse the full large-cap universe in parallel and return the top_n
    buy candidates ranked by health_score.

    Args:
        top_n   : number of top results to return (default 10)
        period  : yfinance period string passed to each analyze() call
        workers : thread-pool size (default 10)

    Returns:
        {
          "scan_date":       str,
          "tickers_scanned": int,
          "tickers_failed":  int,
          "top_picks":       [{ rank, ticker, verdict, health_score,
                                 price, returns.1m, returns.1y,
                                 volatility.sharpe_ratio, summary }, ...],
          "all_scores":      { ticker: health_score, ... },
          "recommendation":  str   ← plain-English top pick sentence
        }
    """
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_safe_analyze, t, period): t for t in UNIVERSE}
        for fut in as_completed(futures):
            results.append(fut.result())

    succeeded = [r for r in results if r.get("_ok")]
    failed = [r["ticker"] for r in results if not r.get("_ok")]

    # Sort: verdict tier first, then health_score descending
    succeeded.sort(
        key=lambda r: (
            _VERDICT_RANK.get(r.get("verdict", "HOLD"), 2),
            -(r.get("health_score") or 0),
        )
    )

    top = succeeded[:top_n]

    top_picks = []
    for rank, r in enumerate(top, start=1):
        top_picks.append({
            "rank": rank,
            "ticker": r["ticker"],
            "verdict": r.get("verdict"),
            "health_score": r.get("health_score"),
            "price": r.get("price", {}).get("current"),
            "return_1m": r.get("returns", {}).get("1m"),
            "return_1y": r.get("returns", {}).get("1y"),
            "sharpe": r.get("volatility", {}).get("sharpe_ratio"),
            "rsi": r.get("momentum", {}).get("rsi_14"),
            "macd_trend": r.get("momentum", {}).get("macd_trend"),
            "bb_zone": r.get("bollinger", {}).get("zone"),
            "golden_cross": r.get("trend", {}).get("golden_cross"),
            "summary": r.get("summary", ""),
        })

    all_scores = {
        r["ticker"]: r.get("health_score")
        for r in succeeded
    }

    # Plain-English recommendation
    if top_picks:
        best = top_picks[0]
        rec = (
                f"Top pick: {best['ticker']} "
                f"(score {best['health_score']}/10, {best['verdict']}, "
                f"Sharpe {best['sharpe']}, 1Y return {best['return_1y']}%). "
                f"Next: " +
                ", ".join(
                    f"{p['ticker']} ({p['health_score']})"
                    for p in top_picks[1:4]
                ) + "."
        )
    else:
        rec = "No strong buy candidates found in current scan."

    return {
        "scan_date": str(date.today()),
        "tickers_scanned": len(succeeded),
        "tickers_failed": len(failed),
        "failed_tickers": failed,
        "top_picks": top_picks,
        "all_scores": dict(sorted(all_scores.items(), key=lambda x: -(x[1] or 0))),
        "recommendation": rec,
    }
