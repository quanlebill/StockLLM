# Variables Calculable from Retrieved Data

These variables from `baseknowledge/stock_prediction_variables_1week.md` do NOT require a separate API call.
They can be derived from data already pulled by the extraction scripts in this folder.

---

## From `daily_adjusted_price.py` (daily OHLCV)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Support level | Rolling maximum close/high over past N days (e.g. 20-day) | `high`, `close` |
| Resistance level | Rolling minimum close/low over past N days (e.g. 20-day) | `low`, `close` |
| Gap-up event | `(open_today - close_yesterday) / close_yesterday > threshold` (e.g. > +1%) | `open`, `close` |
| Gap-down event | `(open_today - close_yesterday) / close_yesterday < -threshold` | `open`, `close` |
| Realized Volatility (RV) | Standard deviation of daily log returns over a rolling window (e.g. 10-day, 21-day) | `adjusted_close` |
| Price momentum (5-day ROC) | `(close_today - close_5_days_ago) / close_5_days_ago * 100` | `close` (alternative to ROC script) |
| Price momentum (10-day ROC) | `(close_today - close_10_days_ago) / close_10_days_ago * 100` | `close` (alternative to ROC script) |

---

## From `bollinger_bands.py` (upper, middle, lower bands)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Bollinger Band width | `upper_band - lower_band` | `upper_band`, `lower_band` |
| Bollinger Band position (% B) | `(close - lower_band) / (upper_band - lower_band)` | `upper_band`, `lower_band` + close from price data |

---

## From `historical_options_chain.py` (options chain with IV, Greeks, OI, volume)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Put/Call ratio (volume) | `sum(volume where type=put) / sum(volume where type=call)` | `type`, `volume` |
| Put/Call ratio (open interest) | `sum(open_interest where type=put) / sum(open_interest where type=call)` | `type`, `open_interest` |
| Gamma exposure (by strike) | `gamma * open_interest * 100 * spot_price` summed by strike and aggregated | `gamma`, `open_interest`, `strike` |
| Net dealer gamma exposure (GEX) | `sum(call gamma exposure) - sum(put gamma exposure)` | `gamma`, `open_interest`, `type` |
| IV vs Realized Volatility spread | `implied_volatility - realized_volatility` (RV from daily price data) | `implied_volatility` + RV from OHLCV |

---

## From `market_indices_daily_price.py` (SPY, QQQ, VIX daily)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Broad market trend (5-day direction) | `(close_today - close_5_days_ago) / close_5_days_ago` for SPY and QQQ | `symbol`, `close` |
| VIX 1-day change | `vix_today - vix_yesterday` | `close` where `symbol = VIX` |

---

## From `sector_etf_daily_price.py` (sector ETF prices)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Sector ETF relative strength vs. SPY | `(sector_etf_return - spy_return)` over the same period | `close`, `symbol` (joined with SPY from market indices) |

---

## From `extended_hours_intraday_price.py` (intraday with extended hours)

| Variable | How to Calculate | Source Columns |
|---|---|---|
| Pre-market % change | `(last pre-market close - prior regular session close) / prior regular session close` | `datetime`, `close`, `open` |
| After-hours % change | `(after-hours close - regular session close) / regular session close` | `datetime`, `close` |

---

## Variables NOT Available via Alpha Vantage or Yfinance

These variables require specialized data providers and cannot be retrieved or calculated from the above:

| Variable | Reason |
|---|---|
| Bid-ask spread changes | Requires Level 2 / tick data (not in Alpha Vantage free/premium tier) |
| Order book depth imbalance | Requires real-time Level 2 order book data |
| Dark pool / block trade activity | Requires FINRA ATS data or specialized providers (e.g. Quandl, Cboe) |
| Short interest ratio & days-to-cover | Requires FINRA short interest reports or exchange data (bi-monthly, not real-time) |
| Social media sentiment (Reddit WSB, Twitter/X, StockTwits) | Requires social API access (Twitter v2 API, Reddit API, StockTwits API) |
| Analyst upgrade/downgrade (past week) | Not available in Alpha Vantage — requires providers like Refinitiv, Bloomberg, or Benzinga |
| Fed speaker schedule | Not available in Alpha Vantage — available via Federal Reserve calendar or scrapers |
