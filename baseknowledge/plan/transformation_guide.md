## FOR 1 WEEK STOCK PREDICTION
### Have
- `PRICE`, `CHANGE_PCT`, `VOLUME` — current price action (MART__STOCK_DETAIL)
- `PUT_CALL_RATIO`, `OPTIONS_VOLUME` — options flow proxy (MART__STOCK_DETAIL)
- `IMPLIED_VOLATILITY_PCT`, `IV_RANK_PCT`, `IV_PERCENTILE_PCT`, `AVG_IV_30D_PCT`, `IV_HIGH/LOW_52W_PCT` — full IV surface (MART__STOCK_DETAIL)
- `HISTORICAL_VOLATILITY_30D_PCT`, `IV_HV_RATIO` — IV vs realized vol (MART__STOCK_DETAIL)
- `MEETING_DATE`, `PROBABILITY_PCT` — upcoming FOMC flag (MART__FOMC_PROBABILITIES)
- `CHANGE_1W_PCT` per sector — sector relative strength (MART__SECTOR_PERFORMANCE)

### Computable from Existing Data
| Computed Variable | Source |
|---|---|
| IV vs RV spread | `CURRENT_IV_PCT - HISTORICAL_VOLATILITY_30D_PCT` (MART__STOCK_DETAIL) |
| Stock vs sector relative strength | `STOCK CHANGE_PCT / sector CHANGE_PCT` (MART__STOCK_DETAIL + MART__SECTOR_PERFORMANCE) |
| Rate cut/hike probability | `PROBABILITY_PCT` where target < or > current rate (MART__FOMC_PROBABILITIES) |
| 10Y yield daily change | lag on `YIELD_10Y` (MART__YIELD_CURVE) |