import yfinance as yf
import pandas as pd
import numpy as np

"""
Yield Spread: ^TYX
Sectors: https://finance.yahoo.com/research-hub/screener/sec-ind_sec-top-etfs_financial-services/

Technology	XLK
Financials	XLF
Health Care	XLV
Consumer Discretionary	XLY
Consumer Staples	XLP
Energy	XLE
Industrials	XLI
Materials	XLB
Utilities	XLU
Real Estate	XLRE
Communication Services	XLC

relative_strength = sector_ret - market_ret, market ret is ^GSPC


Boiling Band 
Middle band = moving average
Upper band = MA + 2×std
Lower band = MA − 2×std
| Bollinger Band Width | `upper_band - lower_band` | Bollinger Bands |
| Bollinger Band %B | `(close - lower_band) / (upper_band - lower_band)` | Bollinger Bands + OHLCV |


ROC (5d/10d), OBV, ATR
ROC: rate of change of stock
OBV: 
df['obv'] = 0

for i in range(1, len(df)):
    if df['Close'].iloc[i] > df['Close'].iloc[i-1]:
        df.loc[df.index[i], 'obv'] = df['obv'].iloc[i-1] + df['Volume'].iloc[i]
    elif df['Close'].iloc[i] < df['Close'].iloc[i-1]:
        df.loc[df.index[i], 'obv'] = df['obv'].iloc[i-1] - df['Volume'].iloc[i]
    else:
        df.loc[df.index[i], 'obv'] = df['obv'].iloc[i-1]

ATR:
TR = max(
    High − Low,
    |High − Prev Close|,
    |Low − Prev Close|
)

"""
NVDA = yf.download("XLC", period="2y").reset_index()
ticker = yf.Ticker("NVDA")
print(NVDA)


"""
sp500 = yf.download("^GSPC", period="2y", progress=True)
vix = yf.download("^VIX", period="2y", progress=True)
stock = ["NVDA"]
df = yf.download(stock[0], period="2y")
#return
df['ret_1d'] = df['Close'].pct_change(1)
df['ret_3d'] = df['Close'].pct_change(3)
df['ret_5d'] = df['Close'].pct_change(5)

df['ma5'] = df['Close'].rolling(5).mean()
df['ma10'] = df['Close'].rolling(10).mean()

df['vol_ma5'] = df['Volume'].rolling(5).mean()
df['vol_ratio'] = df['Volume'].squeeze()  / df['vol_ma5'].squeeze()

df["volatility"] = df['Close'].pct_change().rolling(5).std()

df['sp500_ret'] = sp500['Close'].pct_change()
df['relative_strength'] = df['ret_5d'] - df['sp500_ret'].rolling(5).sum()

df['price_ma5_diff'] = df['Close'].squeeze() - df['ma5'].squeeze()
df['zscore'] = (df['Close'].squeeze() - df['ma5'].squeeze()) / df['Close'].rolling(5).std().squeeze()

delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

ema12 = df['Close'].ewm(span=12).mean()
ema26 = df['Close'].ewm(span=26).mean()
df['macd'] = ema12 - ema26

for lag in [1, 2, 3, 5]:
    df[f'ret_1d_lag_{lag}'] = df['ret_1d'].shift(-lag)

df.dropna(inplace=True)
df = df.iloc[:,5:]

corr_matrix = df.corr().abs()
corr_matrix = corr_matrix.to_numpy()
corr_matrix = corr_matrix * (np.triu(np.ones(corr_matrix.shape), k=1))

print(len(df.iloc[0]))

from statsmodels.stats.outliers_influence import variance_inflation_factor
import statsmodels.api as sm

# Add constant
X_with_const = sm.add_constant(df)

vif_data = pd.DataFrame()
vif_data["Variable"] = X_with_const.columns
vif_data["VIF"] = [
    variance_inflation_factor(X_with_const.values, i)
    for i in range(X_with_const.shape[1])
]

print(vif_data["VIF"])
print(df.head())
"""