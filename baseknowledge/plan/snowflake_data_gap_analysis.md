# Snowflake Data Gap Analysis vs. Stock Prediction Variables

## Tables Available in Snowflake

| Table | What It Contains |
|---|---|
| `MART__STOCK_DETAIL` | Per-ticker: price, volume, change%, market cap, P/E, P/B, ROE, dividend yield, put/call ratio, options volume, IV (current/rank/percentile/30d avg/52W high-low), HV 30d, IV/HV ratio, fair value, price-to-fair-value, star rating, economic moat, uncertainty, sector, industry, country |
| `MART__SECTOR_PERFORMANCE` | Per sector: ETF close, volume, 52W high/low, change (1D/1W/1M/3M/YTD), P/E, forward P/E, P/B, ROE, ROA, operating/net/gross margin, dividend yield, market cap |
| `MART__YIELD_CURVE` | All tenors: 1M/3M/6M/1Y/2Y/5Y/10Y/30Y yields + 10Y-2Y and 10Y-3M spreads (daily) |
| `MART__FED_FUNDS_DAILY` | Daily fed funds rate, target lower/upper bound |
| `MART__FED_FUNDS_MONTHLY` | Monthly fed funds rate |
| `MART__INFLATION` | CPI, core CPI, PCE, core PCE, PPI, trimmed mean PCE, median CPI (levels + YoY) |
| `MART__NONFARM_PAYROLLS` | Monthly NFP level |
| `MART__GDP` | GDP nominal/real/PPP, per capita, growth (annual by country) |
| `MART__CONSUMER_SENTIMENT` | Monthly consumer sentiment score by country |
| `MART__COUNTRIES` | Country reference (name, ISO codes) |
| `MART__STANDARD_DAY/MONTH/YEAR` | Date dimension tables |

---

## 1-Week Horizon

### Have
- `PRICE`, `CHANGE_PCT`, `VOLUME` — current price action (MART__STOCK_DETAIL)
- `PUT_CALL_RATIO`, `OPTIONS_VOLUME` — options flow proxy (MART__STOCK_DETAIL)
- `IMPLIED_VOLATILITY_PCT`, `IV_RANK_PCT`, `IV_PERCENTILE_PCT`, `AVG_IV_30D_PCT`, `IV_HIGH/LOW_52W_PCT` — full IV surface (MART__STOCK_DETAIL)
- `HISTORICAL_VOLATILITY_30D_PCT`, `IV_HV_RATIO` — IV vs realized vol (MART__STOCK_DETAIL)
- `REPORT_DATE`, `EPS_SURPRISE_PCT` — earnings calendar flag + post-earnings drift (MART__EARNINGS_CALENDAR)
- `MEETING_DATE`, `PROBABILITY_PCT` — upcoming FOMC flag (MART__FOMC_PROBABILITIES)
- `CHANGE_1W_PCT` per sector — sector relative strength (MART__SECTOR_PERFORMANCE)
- `ADVANCE_DECLINE_RATIO`, `NEW_52W_HIGHS/LOWS`, `PCT_ABOVE_50DMA/200DMA` — broad market breadth (MART__MARKET_BREADTH)

claude mcp add -t http alphavantage https://mcp.alphavantage.co/mcp?apikey=7TAALYO7AU0IJAAR


### Computable from Existing Data
| Computed Variable | Source |
|---|---|
| IV vs RV spread | `CURRENT_IV_PCT - HISTORICAL_VOLATILITY_30D_PCT` (MART__STOCK_DETAIL) |
| IV rank percentile position | `IV_RANK_PCT` already present |
| Days to next FOMC | `MEETING_DATE - current date` (MART__FOMC_PROBABILITIES) |
| Days to next earnings | `REPORT_DATE - current date` (MART__EARNINGS_CALENDAR) |
| Revenue surprise % | `(ACTUAL_REVENUE_USD - EST_REVENUE_USD) / EST_REVENUE_USD` (MART__EARNINGS_CALENDAR) |
| Stock vs sector relative strength | `STOCK CHANGE_PCT / sector CHANGE_PCT` (MART__STOCK_DETAIL + MART__SECTOR_PERFORMANCE) |
| Rate cut/hike probability | `PROBABILITY_PCT` where target < or > current rate (MART__FOMC_PROBABILITIES) |
| 10Y yield daily change | lag on `YIELD_10Y` (MART__YIELD_CURVE) |

### Missing (Need New Data Sources)
- **Historical OHLCV** — no price history per stock; blocks ALL technical indicators (RSI, MACD, ATR, OBV, Bollinger Bands, VWAP, momentum ROC, support/resistance)
- **Short interest** (ratio, days-to-cover) — no FINRA/broker data
- **News sentiment** — no NLP pipeline / news feed
- **Social sentiment** (Reddit, Twitter/X, StockTwits)
- **Analyst upgrade/downgrade events** (last 5 days)
- **Insider Form 4 filings** (buy/sell last 5 days)
- **VIX** (market fear gauge; breadth is a rough proxy but not VIX itself)
- **Pre-market / after-hours price**
- **Bid-ask spread, order book depth, dark pool flow** (microstructure)

---

## 1-Month Horizon

### Have
- `PE_RATIO`, `PB_RATIO`, `ROE_PCT`, `DIVIDEND_YIELD_PCT`, `MARKET_CAP_USD` (MART__STOCK_DETAIL)
- `FORWARD_PE` per sector (MART__SECTOR_PERFORMANCE)
- `ECONOMIC_MOAT`, `STAR_RATING`, `UNCERTAINTY`, `FAIR_VALUE_USD`, `PRICE_TO_FAIR_VALUE` — Morningstar-style qualitative scores (MART__STOCK_DETAIL)
- `EPS_SURPRISE_PCT`, `EST_EPS`, `ACTUAL_EPS`, `EST_REVENUE_USD`, `ACTUAL_REVENUE_USD` (MART__EARNINGS_CALENDAR)
- Sector fundamentals: P/E, forward P/E, P/B, ROE, ROA, margins (MART__SECTOR_PERFORMANCE)
- `CHANGE_1M_PCT`, `CHANGE_3M_PCT` per sector (MART__SECTOR_PERFORMANCE)
- Full yield curve + `SPREAD_10Y_2Y` (MART__YIELD_CURVE)
- Fed funds rate trajectory (MART__FED_FUNDS_DAILY + MONTHLY)
- CPI, PCE, PPI inflation (MART__INFLATION)
- Consumer sentiment trend (MART__CONSUMER_SENTIMENT)
- FOMC meeting calendar with probabilities (MART__FOMC_PROBABILITIES)

### Computable from Existing Data
| Computed Variable | Source |
|---|---|
| Fed rate change direction (MoM) | Lag on `FED_FUNDS_RATE` (MART__FED_FUNDS_MONTHLY) |
| CPI / PCE YoY trend | Rolling diff on `CPI_LEVEL` / `PCE_LEVEL` (MART__INFLATION) |
| Consumer sentiment MoM change | Lag on `CONSUMER_SENTIMENT` (MART__CONSUMER_SENTIMENT) |
| Yield curve steepening/flattening | Change in `SPREAD_10Y_2Y` over time (MART__YIELD_CURVE) |
| Sector RS score (1M) | `stock CHANGE_PCT` vs `sector CHANGE_1M_PCT` (MART__SECTOR_PERFORMANCE) |
| Earnings beat/miss rate (last N quarters) | Hit rate on `EPS_SURPRISE_PCT > 0` (MART__EARNINGS_CALENDAR) |
| Revenue beat/miss rate | `ACTUAL vs EST REVENUE` (MART__EARNINGS_CALENDAR) |
| Stock vs fair value discount/premium | `PRICE_TO_FAIR_VALUE` (already computed in MART__STOCK_DETAIL) |
| FOMC hawkish/dovish signal | Compare `TARGET_RATE_LOWER_PCT` vs current `FED_FUNDS_RATE` (FOMC_PROBABILITIES + FED_FUNDS) |

### Missing
- **Historical OHLCV** — still blocks all technical indicators (20/50 MA, ADX, RS rating)
- **Analyst EPS revision trend** (# upgrades vs. downgrades last 30 days)
- **Institutional ownership change** (13F quarterly filings)
- **Short interest change** (monthly delta)
- **Management guidance** (raised/maintained/lowered flag)
- **30-day news sentiment aggregate**
- **Fund flow data** (ETF inflows/outflows by sector)
- **Credit spreads** (HY vs. IG — not in schema)
- **AAII Bull/Bear survey**
- **Free cash flow yield** (need cash flow statements)
- **PEG ratio** (need EPS growth rate over time)
- **Revenue growth rate** (need historical EPS/revenue from financial statements)

---

## 1-Year Horizon

### Have
- `P/E`, `P/B`, `ROE`, `DIVIDEND_YIELD`, `MARKET_CAP` per stock (MART__STOCK_DETAIL)
- `ECONOMIC_MOAT`, `STAR_RATING`, `FAIR_VALUE`, `PRICE_TO_FAIR_VALUE` (Morningstar quality signals) (MART__STOCK_DETAIL)
- `FORWARD_PE`, sector margins, ROA (MART__SECTOR_PERFORMANCE)
- Full macro suite: GDP growth, CPI/PCE/PPI, NFP, fed funds, yield curve (all tenors), FOMC probabilities (multiple tables)
- Consumer sentiment history (MART__CONSUMER_SENTIMENT)

### Computable from Existing Data
| Computed Variable | Source |
|---|---|
| GDP cycle stage (expansion/contraction) | Sign of `GDP_GROWTH` + trend (MART__GDP) |
| Real interest rate | `YIELD_10Y - CPI YoY` (YIELD_CURVE + INFLATION) |
| Inflation regime (rising/falling/stable) | Rolling trend on `CPI_LEVEL` (MART__INFLATION) |
| Fed tightening/easing cycle | Direction of `FED_FUNDS_RATE` over 12M (MART__FED_FUNDS_MONTHLY) |
| Yield curve inversion flag | `SPREAD_10Y_2Y < 0` (MART__YIELD_CURVE) |
| Sector rotation signal | 3M / YTD change ranking across sectors (MART__SECTOR_PERFORMANCE) |
| Moat + valuation composite score | `ECONOMIC_MOAT` + `PRICE_TO_FAIR_VALUE` + `STAR_RATING` (MART__STOCK_DETAIL) |
| EPS growth rate (if multi-quarter history) | QoQ change in `ACTUAL_EPS` (MART__EARNINGS_CALENDAR) |
| Revenue growth rate | QoQ change in `ACTUAL_REVENUE_USD` (MART__EARNINGS_CALENDAR) |

### Missing
- **Financial statements** (income, balance sheet, cash flow) — blocks FCF, debt/equity, interest coverage, ROIC, net margin trend, R&D spend
- **EV/EBITDA** — needs debt + cash (balance sheet)
- **Price/Sales** — needs revenue per share over time
- **Institutional ownership** (13F) — % and YoY change
- **Insider ownership %** and share buyback activity
- **Analyst 12-month price target** and consensus rating
- **Short interest % of float** and trend
- **ESG scores**
- **Alternative data**: job postings, web traffic, patent filings, earnings call NLP
- **Geopolitical revenue exposure** (revenue by country)
- **M&A / corporate action history**

---

## Priority Gap to Fill

| Priority | Missing Data | Why Critical | Suggested Source |
|---|---|---|---|
| P0 | **Historical OHLCV per stock** | Blocks all technical indicators across all 3 horizons | Yahoo Finance, Polygon.io, Alpha Vantage |
| P1 | **Financial statements** (income/balance sheet/cash flow) | Blocks most 1-year fundamental variables | Alpha Vantage, FMP, SimFin |
| P2 | **Analyst estimates & revisions** | Revision momentum is high-signal for 1M horizon | Alpha Vantage, FMP, Refinitiv |
| P2 | **Short interest** | Key contrarian signal for 1W and 1M | FINRA, Quandl |
| P3 | **News sentiment** | Needed for all 3 horizons | News API + NLP pipeline |
| P3 | **Institutional ownership** (13F) | Long-term signal for 1Y | SEC EDGAR |
| P4 | **VIX** | Better fear gauge than breadth alone | CBOE / Yahoo Finance |
| P4 | **Credit spreads** (HY-IG) | Macro risk signal for 1M/1Y | FRED (already have FredCrawler?) |
