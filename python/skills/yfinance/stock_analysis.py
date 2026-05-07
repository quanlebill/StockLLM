"""
stock_analysis.py — yfinance-based stock health analyser.

Returns a structured dict of computed metrics + interpretation.
Never exposes raw OHLCV price series to the caller.

Public API
----------
analyze(ticker, period="1y") -> dict
"""

import math
from typing import Optional

import numpy as np
import yfinance as yf

# ── constants ────────────────────────────────────────────────────────────────
RISK_FREE_DAILY = 0.045 / 252  # ~4.5 % annual → per-day


# ── helpers ──────────────────────────────────────────────────────────────────

def _rsi(closes: np.ndarray, period: int = 14) -> float:
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _ema(series: np.ndarray, span: int) -> np.ndarray:
    k = 2 / (span + 1)
    ema = np.empty_like(series)
    ema[0] = series[0]
    for i in range(1, len(series)):
        ema[i] = series[i] * k + ema[i - 1] * (1 - k)
    return ema


def _macd(closes: np.ndarray) -> dict:
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = ema12 - ema26
    signal = _ema(macd_line, 9)
    hist = macd_line - signal
    return {
        "macd": round(float(macd_line[-1]), 4),
        "signal": round(float(signal[-1]), 4),
        "hist": round(float(hist[-1]), 4),
        "trend": "bullish" if macd_line[-1] > signal[-1] else "bearish",
    }


def _bollinger(closes: np.ndarray, window: int = 20) -> dict:
    if len(closes) < window:
        return {}
    recent = closes[-window:]
    mid = float(np.mean(recent))
    std = float(np.std(recent, ddof=1))
    upper = mid + 2 * std
    lower = mid - 2 * std
    price = float(closes[-1])
    band_range = upper - lower
    position_pct = round((price - lower) / band_range * 100, 1) if band_range else 50.0
    if position_pct >= 80:
        zone = "overbought"
    elif position_pct <= 20:
        zone = "oversold"
    else:
        zone = "neutral"
    return {
        "upper": round(upper, 2),
        "middle": round(mid, 2),
        "lower": round(lower, 2),
        "position_pct": position_pct,
        "zone": zone,
    }


def _max_drawdown(closes: np.ndarray) -> float:
    peak = closes[0]
    max_dd = 0.0
    for p in closes:
        if p > peak:
            peak = p
        dd = (p - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


def _pct_change(closes: np.ndarray, n_days: int) -> Optional[float]:
    if len(closes) < n_days + 1:
        return None
    base = closes[-(n_days + 1)]
    if base == 0:
        return None
    return round((closes[-1] - base) / base * 100, 2)


def _health_score(metrics: dict) -> tuple[float, str]:
    """
    Score 0-10 from signals. Each signal contributes a weighted point.
    Returns (score, verdict).
    """
    score = 5.0  # neutral baseline

    trend = metrics.get("trend", {})
    mom = metrics.get("momentum", {})
    bb = metrics.get("bollinger", {})
    vol = metrics.get("volatility", {})
    rets = metrics.get("returns", {})

    # ── trend signals ────────────────────────────────────────────────────────
    if trend.get("golden_cross"):
        score += 1.0
    elif trend.get("death_cross"):
        score -= 1.0

    if trend.get("above_ma50"):
        score += 0.5
    else:
        score -= 0.5

    if trend.get("above_ma200"):
        score += 0.5
    else:
        score -= 0.5

    # ── momentum / RSI ───────────────────────────────────────────────────────
    rsi = mom.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 1.5  # oversold — contrarian buy
        elif rsi < 45:
            score += 0.5  # mildly weak
        elif rsi <= 60:
            score += 0.5  # healthy momentum
        elif rsi <= 70:
            score -= 0.25  # slightly elevated
        else:
            score -= 1.0  # overbought

    # ── MACD ─────────────────────────────────────────────────────────────────
    if mom.get("macd_trend") == "bullish":
        score += 0.75
    else:
        score -= 0.75

    # ── Bollinger ────────────────────────────────────────────────────────────
    bb_zone = bb.get("zone")
    if bb_zone == "oversold":
        score += 0.75
    elif bb_zone == "overbought":
        score -= 0.75

    # ── Sharpe ───────────────────────────────────────────────────────────────
    sharpe = vol.get("sharpe_ratio")
    if sharpe is not None:
        if sharpe > 1.5:
            score += 1.0
        elif sharpe > 0.5:
            score += 0.5
        elif sharpe < 0:
            score -= 1.0

    # ── recent return ────────────────────────────────────────────────────────
    r1m = rets.get("1m")
    if r1m is not None:
        if r1m > 5:
            score += 0.5
        elif r1m < -10:
            score -= 0.5

    # ── max drawdown penalty ─────────────────────────────────────────────────
    mdd = metrics.get("max_drawdown_pct")
    if mdd is not None and mdd < -35:
        score -= 1.0

    score = round(max(0.0, min(10.0, score)), 1)

    if score >= 8:
        verdict = "STRONG BUY"
    elif score >= 6.5:
        verdict = "BUY"
    elif score >= 4.5:
        verdict = "HOLD"
    elif score >= 3:
        verdict = "SELL"
    else:
        verdict = "STRONG SELL"

    return score, verdict


# ── public API ───────────────────────────────────────────────────────────────

def analyze(ticker: str, period: str = "1y") -> dict:
    """
    Download stock data via yfinance and return a fully computed analysis dict.

    Args:
        ticker : stock ticker symbol (e.g. "AAPL", "TSLA")
        period : history length passed to yfinance ("6mo", "1y", "2y")

    Returns:
        dict with keys: ticker, price, returns, volatility, spread, trend,
                        momentum, bollinger, volume, max_drawdown_pct
    """
    tk = yf.Ticker(ticker.upper())
    hist = tk.history(period=period)

    if hist.empty or len(hist) < 30:
        return {"error": f"Insufficient data for ticker '{ticker}'"}

    closes = hist["Close"].to_numpy(dtype=float)
    volumes = hist["Volume"].to_numpy(dtype=float)
    dates = hist.index

    current_price = float(closes[-1])

    # ── 52-week range ────────────────────────────────────────────────────────
    w52_high = float(closes.max())
    w52_low = float(closes.min())
    w52_range = w52_high - w52_low
    w52_pos = round((current_price - w52_low) / w52_range * 100, 1) if w52_range else 50.0

    # ── returns ──────────────────────────────────────────────────────────────
    returns_block = {
        "1d": _pct_change(closes, 1),
        "5d": _pct_change(closes, 5),
        "1m": _pct_change(closes, 21),
        "3m": _pct_change(closes, 63),
        "6m": _pct_change(closes, 126),
        "1y": _pct_change(closes, min(252, len(closes) - 1)),
    }

    # ── daily return stats ───────────────────────────────────────────────────
    daily_returns = np.diff(closes) / closes[:-1]
    mean_daily = float(np.mean(daily_returns))
    std_daily = float(np.std(daily_returns, ddof=1))
    ann_vol = round(std_daily * math.sqrt(252) * 100, 2)
    sharpe = round(
        (mean_daily - RISK_FREE_DAILY) / std_daily * math.sqrt(252), 3
    ) if std_daily > 0 else None

    # ── moving averages ──────────────────────────────────────────────────────
    ma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else None
    ma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else None
    above_ma50 = current_price > ma50 if ma50 else None
    above_ma200 = current_price > ma200 if ma200 else None
    golden_cross = (ma50 > ma200) if (ma50 and ma200) else None
    death_cross = (ma50 < ma200) if (ma50 and ma200) else None

    # ── RSI ──────────────────────────────────────────────────────────────────
    rsi = _rsi(closes, 14) if len(closes) > 15 else None
    if rsi is not None:
        if rsi < 30:
            rsi_label = "oversold"
        elif rsi > 70:
            rsi_label = "overbought"
        elif rsi < 45:
            rsi_label = "weak"
        elif rsi > 55:
            rsi_label = "strong"
        else:
            rsi_label = "neutral"
    else:
        rsi_label = None

    # ── MACD ─────────────────────────────────────────────────────────────────
    macd_block = _macd(closes) if len(closes) > 35 else {}

    # ── Bollinger Bands ──────────────────────────────────────────────────────
    bb_block = _bollinger(closes)

    # ── volume ───────────────────────────────────────────────────────────────
    avg_vol20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
    last_vol = float(volumes[-1])
    vol_ratio = round(last_vol / avg_vol20, 2) if avg_vol20 > 0 else None

    # ── max drawdown ─────────────────────────────────────────────────────────
    mdd = _max_drawdown(closes)

    # ── spread (high-low daily) ───────────────────────────────────────────────
    highs = hist["High"].to_numpy(dtype=float)
    lows = hist["Low"].to_numpy(dtype=float)
    daily_spread = highs - lows
    mean_spread = round(float(np.mean(daily_spread)), 4)
    mean_spread_pct = round(float(np.mean(daily_spread / closes)) * 100, 3)

    # ── assemble metrics for scoring ─────────────────────────────────────────
    metrics = {
        "trend": {
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "above_ma50": above_ma50,
            "above_ma200": above_ma200,
        },
        "momentum": {
            "rsi_14": rsi,
            "macd_trend": macd_block.get("trend"),
        },
        "bollinger": bb_block,
        "volatility": {"sharpe_ratio": sharpe},
        "returns": returns_block,
        "max_drawdown_pct": mdd,
    }

    return {
        "ticker": ticker.upper(),
        "period": period,
        "as_of": str(dates[-1].date()),
        "price": {
            "current": round(current_price, 2),
            "52w_high": round(w52_high, 2),
            "52w_low": round(w52_low, 2),
            "52w_position_pct": w52_pos,
        },
        "returns": returns_block,
        "volatility": {
            "mean_daily_return_pct": round(mean_daily * 100, 4),
            "daily_std_pct": round(std_daily * 100, 4),
            "annualised_vol_pct": ann_vol,
            "sharpe_ratio": sharpe,
        },
        "spread": {
            "mean_daily_spread": mean_spread,
            "mean_daily_spread_pct": mean_spread_pct,
        },
        "trend": {
            "ma50": round(ma50, 2) if ma50 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "above_ma50": above_ma50,
            "above_ma200": above_ma200,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
        },
        "momentum": {
            "rsi_14": rsi,
            "rsi_signal": rsi_label,
            "macd": macd_block.get("macd"),
            "macd_signal": macd_block.get("signal"),
            "macd_hist": macd_block.get("hist"),
            "macd_trend": macd_block.get("trend"),
        },
        "bollinger": bb_block,
        "volume": {
            "last": int(last_vol),
            "avg_20d": int(avg_vol20),
            "ratio_vs_avg": vol_ratio,
            "spike": vol_ratio is not None and vol_ratio > 2.0,
        },
        "max_drawdown_pct": mdd,
    }
