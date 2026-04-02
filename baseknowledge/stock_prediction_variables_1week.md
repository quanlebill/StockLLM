# Stock Prediction Variables — 1 Week Horizon

Short-term signals dominate at this horizon. Focus on price momentum, order flow, and near-term sentiment.

## Technical Indicators
- Price momentum (ROC 5, 10 days)
- RSI (14-day)
- MACD (12/26/9)
- Bollinger Bands width & position
- Volume-weighted average price (VWAP)
- Average True Range (ATR) — volatility proxy
- On-Balance Volume (OBV)
- Stochastic Oscillator (%K, %D)
- Support / resistance levels (recent highs/lows)
- Gap-up / gap-down events

## Market Microstructure
- Bid-ask spread changes
- Order book depth imbalance
- Dark pool / block trade activity
- Short interest ratio & days-to-cover
- Options put/call ratio
- Implied volatility (IV) vs. realized volatility (RV)
- Options open interest by strike (gamma exposure)

## News & Sentiment
- News sentiment score (last 1–3 days)
- Social media sentiment (Reddit WSB, Twitter/X, StockTwits)
- Analyst upgrade/downgrade in past week
- Earnings surprise from most recent quarter (post-earnings drift)
- Insider buy/sell filings (Form 4, last 5 days)

## Macro / Market Context
- Broad market trend (S&P 500 / NASDAQ direction last 5 days)
- VIX level and 1-day change
- Sector ETF relative strength
- Pre-market / after-hours price movement

## Calendar Events (within the week)
- Upcoming earnings date flag
- Fed speaker schedule
- Economic data releases (CPI, PPI, NFP, etc.)
- Ex-dividend date proximity


## Tables Available in Snowflake
| Table | What It Contains |
|---|---|
| `MART__YIELD_CURVE` | All tenors: 1M/3M/6M/1Y/2Y/5Y/10Y/30Y yields + 10Y-2Y and 10Y-3M spreads (daily) |
| `MART__FED_FUNDS_DAILY` | Daily fed funds rate, target lower/upper bound |
| `MART__FED_FUNDS_MONTHLY` | Monthly fed funds rate |
| `MART__INFLATION` | CPI, core CPI, PCE, core PCE, PPI, trimmed mean PCE, median CPI (levels + YoY) |
| `MART__NONFARM_PAYROLLS` | Monthly NFP level |
| `MART__GDP` | GDP nominal/real/PPP, per capita, growth (annual by country) |
| `MART__COUNTRIES` | Country reference (name, ISO codes) |
| `MART__STANDARD_DAY/MONTH/YEAR` | Date dimension tables |
