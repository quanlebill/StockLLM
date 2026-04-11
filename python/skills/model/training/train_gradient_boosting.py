"""
Gradient Boosting for 1-week stock prediction (NVDA)
Reasoning grounded in Top-Down Strategy: Macro → Sector → Stock
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64, io, warnings
from datetime import datetime

from sklearn.ensemble import (GradientBoostingClassifier, ExtraTreesClassifier,
                              RandomForestClassifier)
from sklearn.base import clone
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (precision_recall_curve, roc_curve, auc,
                             classification_report, average_precision_score,
                             roc_auc_score)
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

from snowflake_io import fetch

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# Financial Reasoning (Top-Down Strategy anchored)
# ─────────────────────────────────────────────────────────────────────────────
FINANCIAL_REASONING = {
    'STOCK_RETURN_1DAY': {
        'layer': 'Stock Scan',
        'reasoning': (
            'Short-term momentum. Finviz & Barchart scan filters require Week performance +2% or more. '
            'A 1-day return captures whether yesterday\'s price action sustains into the next week — '
            'momentum continuation is a core entry signal in the top-down stock scan layer.'
        ),
    },
    'STOCK_RETURN_3DAY': {
        'layer': 'Stock Scan',
        'reasoning': (
            '3-day momentum window. Sits between the 1-day noise and the 5-day trend signal. '
            'In the stock scan layer, this window captures whether a recent catalyst (earnings beat, '
            'sector news) is translating into sustained buying pressure over several sessions.'
        ),
    },
    'STOCK_RETURN_5DAY': {
        'layer': 'Stock Scan',
        'reasoning': (
            '5-day (weekly) return — directly corresponds to the 1-week prediction horizon. '
            'This is the momentum of the current week. Strong positive 5-day return = stock is in '
            'the Leading quadrant on RRG. Momentum continuation is statistically documented in '
            'short-term windows. High correlation with 1-day and 3-day returns is expected and '
            'financially explained: they share overlapping price data.'
        ),
    },
    'MA5': {
        'layer': 'Stock Scan',
        'reasoning': (
            '5-day moving average. In top-down strategy, MA crossovers (SMA20 > SMA50) are primary '
            'Barchart scan filters. MA5 represents the very short-term trend baseline. '
            'High correlation with MA10 is structurally expected — both are moving averages of the '
            'same price series over similar windows. They measure the same underlying concept (trend) '
            'at different speeds. If flagged multicollinear, retain MA10 as it smooths more noise.'
        ),
    },
    'MA10': {
        'layer': 'Stock Scan',
        'reasoning': (
            '10-day moving average. Closer to the SMA20 referenced in Barchart screener. '
            'Acts as a short-term trend confirmation. When price > MA10, stock is in a local uptrend — '
            'a necessary condition before the top-down framework would consider entry. '
            'Correlation with MA5 is expected (structural overlap in calculation).'
        ),
    },
    'VOL_MA5': {
        'layer': 'Stock Scan',
        'reasoning': (
            '5-day average volume baseline. In top-down strategy, volume > 20-day average (1.5x) '
            'confirms a breakout is real and not a false signal. VOL_MA5 provides the short-term '
            'baseline against which current volume is compared. Correlated with VOL_RATIO by construction '
            '(ratio denominator).'
        ),
    },
    'VOL_RATIO': {
        'layer': 'Stock Scan',
        'reasoning': (
            'Volume ratio (current vs 5-day avg). This is the direct implementation of the Barchart '
            'filter: "Today\'s Volume > 20-day Average Volume (1.5x)." A vol_ratio > 1.5 signals '
            'institutional participation behind the price move — crucial for confirming breakouts. '
            'Strong financial justification: high volume on up days = accumulation. Correlated with '
            'VOL_MA5 by construction but captures different information (relative surge vs. absolute level).'
        ),
    },
    'VOLATILITY': {
        'layer': 'Stock Scan / Risk',
        'reasoning': (
            'Realized volatility (5-day rolling std of daily returns). In top-down strategy, volatility '
            'is tracked via IV Percentile: IV% < 25 = buy options cheap; IV% > 75 = sell premium. '
            'High realized volatility precedes regime shifts and affects optimal strategy selection. '
            'For a directional 1-week model, high volatility = uncertainty, widening the outcome distribution.'
        ),
    },
    'PRICE_MA5_DIFF': {
        'layer': 'Stock Scan',
        'reasoning': (
            'Price minus MA5 — measures how far price has deviated from its short-term mean. '
            'Positive = price is extended above MA5 (potential mean reversion). '
            'Negative = price is below MA5 (potential support test or bearish). '
            'Top-down strategy monitors proximity to support/resistance. Strong structural correlation '
            'with ZSCORE expected (ZSCORE normalizes the same difference by standard deviation). '
            'If both flagged, ZSCORE is preferred as it is scale-invariant.'
        ),
    },
    'ZSCORE': {
        'layer': 'Stock Scan',
        'reasoning': (
            'Standardized deviation of price from MA5. Captures mean-reversion potential. '
            'Z-score > 2 = price extended (overbought zone). Z-score < -2 = oversold. '
            'This aligns with support/resistance analysis in top-down strategy: "broke down near support" '
            'is a fundamental scan criterion. Highly correlated with PRICE_MA5_DIFF by construction — '
            'they encode the same signal with different normalization.'
        ),
    },
    'VIX_1DAY_CHANGE': {
        'layer': 'Macro',
        'reasoning': (
            'Daily change in the VIX fear index — the top-most variable in the top-down pyramid. '
            '"Step 1 of the 7-step checklist before placing a trade: VIX < 25? Is the market not in '
            'a strong downtrend?" A spike in VIX signals fear/risk-off, directly suppressing bullish '
            'setups. VIX change is a regime signal: rising VIX = shift to defensive posture, '
            'falling VIX = improving confidence. Causally upstream of all stock-level signals.'
        ),
    },
    'SECTOR_RETURN_5DAY': {
        'layer': 'Sector',
        'reasoning': (
            'Technology sector (XLK) 5-day return. Top-down research: 40-60% of a stock\'s performance '
            'comes from its sector. RRG quadrant analysis: Leading sector = strong relative strength + '
            'high momentum. NVDA is in XLK (Technology). Sector tailwind is a prerequisite before '
            'stock-level entry in the top-down framework. Correlated with RELATIVE_STRENGTH structurally '
            '(relative strength is computed vs SP500 which also reflects sector flows).'
        ),
    },
    'YIELD_CURVE_1DAY_CHANGE': {
        'layer': 'Macro',
        'reasoning': (
            'Daily change in the yield spread (10Y-2Y or 10Y-3M). Top-down framework: '
            '"Inverse yield curve (10Y < 2Y) = recession warning." Yield curve steepening is '
            'risk-on (growth expectations rising); flattening/inversion is risk-off. '
            'For a growth stock like NVDA, rate sensitivity is high: rising rates → P/E compression. '
            'Causally anchored at the macro layer — affects all downstream layers.'
        ),
    },
    'RELATIVE_STRENGTH': {
        'layer': 'Sector / Stock Scan',
        'reasoning': (
            'Stock 5-day return minus SP500 5-day return — the core RRG axis. '
            'Top-down strategy: stocks in the Leading RRG quadrant (positive RS + momentum) '
            'are prioritized for entry. Positive relative strength = NVDA outperforms market, '
            'indicating institutional accumulation and sector leadership. '
            'Correlated with SECTOR_RETURN_5DAY (both capture market-relative performance) but '
            'RELATIVE_STRENGTH is stock-specific vs sector-level.'
        ),
    },
    'OBV': {
        'layer': 'Stock Scan',
        'reasoning': (
            'On-Balance Volume — cumulative volume-weighted price direction. '
            'OBV rising with price = institutional accumulation (confirming trend). '
            'OBV diverging from price = distribution (warning sign). '
            'Top-down scan layer: "Today\'s Volume > 20-day Average Volume (1.5x)" is the '
            'entry filter; OBV extends this to a cumulative trend signal. '
            'OBV and VOL_RATIO measure volume from different angles — ratio captures daily surges, '
            'OBV captures sustained directional volume flow.'
        ),
    },
    'RSI': {
        'layer': 'Stock Scan',
        'reasoning': (
            'Relative Strength Index (14-day). Momentum oscillator used in Barchart screener. '
            'RSI < 30 = oversold (potential reversal buy); RSI > 70 = overbought (caution). '
            'In top-down strategy, RSI confirms whether a stock has the momentum to continue. '
            'Structurally correlated with STOCK_RETURN_* features (RSI is derived from price changes). '
            'However RSI provides a bounded, normalized signal where raw returns do not.'
        ),
    },
    'MACD': {
        'layer': 'Stock Scan',
        'reasoning': (
            'MACD histogram (MACD line minus signal line). Captures convergence/divergence of '
            '12-day and 26-day EMAs. A positive histogram = bullish momentum building; '
            'negative = bearish. In top-down strategy, MACD crossover signals stock-level '
            'entry timing after macro and sector conditions are confirmed. '
            'Structurally correlated with MA5/MA10 (all EMA-based), but MACD specifically '
            'captures the rate of change of momentum rather than absolute trend level.'
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Helper: plot to base64
# ─────────────────────────────────────────────────────────────────────────────
def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded

# ─────────────────────────────────────────────────────────────────────────────
# Helper: train and evaluate
# ─────────────────────────────────────────────────────────────────────────────
def train_eval(X_train, y_train, X_test, y_test, label=''):
    clf = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=3, subsample=0.8, random_state=42
    )
    clf.fit(X_train, y_train)
    y_prob = clf.predict_proba(X_test)[:, 1]
    y_pred = clf.predict(X_test)
    roc_auc = roc_auc_score(y_test, y_prob)
    avg_prec = average_precision_score(y_test, y_prob)
    report = classification_report(y_test, y_pred, output_dict=True)
    return clf, y_prob, y_pred, roc_auc, avg_prec, report

# ─────────────────────────────────────────────────────────────────────────────
# Data pipeline helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_conversation(key: str) -> tuple:
    """Fetch table_names and column_names from the CONVERSATION table by key."""
    df_conv = fetch(
        "CONVERSATION",
        query=(
            "SELECT TABLE_NAMES, COLUMN_NAMES "
            "FROM STOCKLLM.dbt_stock.CONVERSATION "
            f"WHERE KEY = '{key}' "
            "LIMIT 1"
        ),
    )
    if df_conv.empty:
        raise KeyError(f"No conversation found for key: {key}")
    row = df_conv.iloc[0]
    table_names = json.loads(row["TABLE_NAMES"])
    column_names = json.loads(row["COLUMN_NAMES"])
    return table_names, column_names


def _build_dataframe(table_names: list, column_names: dict) -> pd.DataFrame:
    """Fetch each table with its selected columns and merge on the timestamp column."""
    dfs = []
    for tbl in table_names:
        cols = [c.upper() for c in column_names.get(tbl, [])]
        if not cols:
            continue
        col_list = ", ".join(f'"{c}"' for c in cols)
        df_tbl = fetch(tbl, query=f"SELECT {col_list} FROM STOCKLLM.dbt_stock.{tbl}")
        df_tbl.columns = [c.upper() for c in df_tbl.columns]
        dfs.append(df_tbl)

    if not dfs:
        raise ValueError("No data fetched — check table_names and column_names in the conversation.")

    if len(dfs) == 1:
        return dfs[0]

    # Merge all tables on their first timestamp/date column
    result = dfs[0]
    merge_col = next(
        (c for c in result.columns if "TIMESTAMP" in c or "DATE" in c),
        None,
    )
    for df_other in dfs[1:]:
        other_merge_col = next(
            (c for c in df_other.columns if "TIMESTAMP" in c or "DATE" in c),
            merge_col,
        )
        if merge_col and other_merge_col:
            result = result.merge(
                df_other.rename(columns={other_merge_col: merge_col}),
                on=merge_col,
                how="inner",
            )
        else:
            result = pd.concat([result, df_other], axis=1)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main training function
# ─────────────────────────────────────────────────────────────────────────────

def run_training(key: str) -> str:
    """
    Full training + data pipeline.

    Args:
        key: Conversation key returned by save_conversation() in the MCP server.
             Used to retrieve the table/column selection from STOCKLLM.dbt_stock.CONVERSATION.

    Returns:
        Path to the saved HTML report.
    """
    # ── 0. Load conversation ──────────────────────────────────────────────────
    print("=" * 60)
    print(f"Loading conversation key: {key}")
    table_names, column_names = _fetch_conversation(key)
    print(f"  Tables: {table_names}")
    print(f"  Columns per table: { {t: len(c) for t, c in column_names.items()} }")

    # ── 1. Fetch data ─────────────────────────────────────────────────────────
    print("\nFetching data from Snowflake...")
    df = _build_dataframe(table_names, column_names)

    # Snowflake returns uppercase column names
    df.columns = [c.upper() for c in df.columns]

    # Identify the timestamp column
    ts_col = next((c for c in df.columns if "TIMESTAMP" in c or c == "DATE"), "TRADE_TIMESTAMP")

    numeric_cols = [c for c in df.columns if c != ts_col]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
    df = df.sort_values(ts_col).reset_index(drop=True)
    print(f"  Shape: {df.shape}")
    if not df[ts_col].isna().all():
        print(f"  Date range: {df[ts_col].min().date()} to {df[ts_col].max().date()}")

    # ── 2. Engineer OBV, RSI, MACD (only when raw price/volume columns are present) ──
    if 'STOCK_CLOSE' in df.columns and 'STOCK_VOLUME' in df.columns:
        print("\nEngineering OBV, RSI, MACD...")
        close  = df['STOCK_CLOSE']
        volume = df['STOCK_VOLUME']

        # OBV
        obv = [0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i - 1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i - 1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])
        df['OBV'] = obv

        # RSI (14-day)
        delta    = close.diff()
        avg_gain = delta.clip(lower=0).rolling(14).mean()
        avg_loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs       = avg_gain / avg_loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD histogram (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        df['MACD'] = (macd_line - macd_line.ewm(span=9, adjust=False).mean()) / macd_line.ewm(span=9, adjust=False).mean()
    else:
        close = df.select_dtypes(include='number').iloc[:, 0]  # fallback for target computation

    # ── 3. Target: next-5-day forward return > 0 ─────────────────────────────
    df['TARGET'] = (close.shift(-5) / close - 1 > 0).astype(int)

    # Derive FEATURE_COLS dynamically: all numeric columns except timestamp/close/volume
    _exclude = {ts_col, 'STOCK_CLOSE', 'STOCK_VOLUME', 'TARGET'}
    FEATURE_COLS = [
        c for c in df.columns
        if c not in _exclude
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    df_model = df[FEATURE_COLS + ['TARGET', ts_col]].dropna().reset_index(drop=True)
    print(f"  Model rows after dropna: {len(df_model)}")
    print(f"  Feature columns ({len(FEATURE_COLS)}): {FEATURE_COLS}")

    X_all = df_model[FEATURE_COLS]
    y_all = df_model['TARGET']
    n_features = len(FEATURE_COLS)
    parc_threshold = 2 / np.sqrt(n_features)

    # ── 4. PARC (max pairwise absolute Pearson correlation per feature) ─────────
    print("\nComputing PARC and VIF...")
    corr_matrix = X_all.corr().abs()
    corr_no_diag = corr_matrix.values.copy()
    np.fill_diagonal(corr_no_diag, 0)
    corr_matrix = pd.DataFrame(corr_no_diag, index=corr_matrix.index, columns=corr_matrix.columns)
    parc = corr_matrix.max()

    # ── 5. VIF ───────────────────────────────────────────────────────────────
    scaler   = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X_all), columns=FEATURE_COLS)
    vif      = {col: variance_inflation_factor(X_scaled.values, i)
                for i, col in enumerate(FEATURE_COLS)}

    # ── 6. Feature selection decisions ───────────────────────────────────────
    decisions        = {}
    drop_features    = []
    concern_features = []
    keep_features    = []

    for col in FEATURE_COLS:
        v, p = vif[col], parc[col]
        if v > 15 and p > parc_threshold:
            decisions[col] = 'DROP'
            drop_features.append(col)
        elif v > 15 and p <= parc_threshold:
            decisions[col] = 'CONCERNING'
            concern_features.append(col)
        else:
            decisions[col] = 'KEEP'
            keep_features.append(col)

    # Final features = keep + concerning (all non-dropped)
    final_features = keep_features + concern_features

    print(f"\n  PARC threshold: {parc_threshold:.4f}")
    print(f"  DROP       : {drop_features}")
    print(f"  CONCERNING : {concern_features}")
    print(f"  KEEP       : {keep_features}")
    print(f"  FINAL      : {final_features}")

    # ── 7. Train / test split (time-series: last 20% as test) ────────────────
    split_idx   = int(len(df_model) * 0.8)
    train_df    = df_model.iloc[:split_idx]
    test_df     = df_model.iloc[split_idx:]

    X_train_arr = train_df[final_features].values
    X_test_arr  = test_df[final_features].values
    y_train     = train_df['TARGET'].values
    y_test      = test_df['TARGET'].values

    # ── 8. Layer-1 base models — OOF stacking ────────────────────────────────
    print("\nBuilding stacking ensemble ...")
    print("  Layer 1 : GradientBoosting | ExtraTrees | RandomForest")
    print("  Layer 2 : GradientBoosting blender\n")

    BASE_MODELS = {
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=3,
            subsample=0.8, random_state=42),
        'ExtraTrees': ExtraTreesClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=5, random_state=42),
        'RandomForest': RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=5, random_state=42),
    }

    tscv      = TimeSeriesSplit(n_splits=5)
    n_base    = len(BASE_MODELS)
    oof_train = np.zeros((len(X_train_arr), n_base))
    oof_test  = np.zeros((len(X_test_arr),  n_base))
    layer1_results = {}

    for j, (name, model) in enumerate(BASE_MODELS.items()):
        oof = np.zeros(len(X_train_arr))
        fold_test_preds = []
        for fold_tr_idx, fold_val_idx in tscv.split(X_train_arr):
            m = clone(model)
            m.fit(X_train_arr[fold_tr_idx], y_train[fold_tr_idx])
            oof[fold_val_idx] = m.predict_proba(X_train_arr[fold_val_idx])[:, 1]
            fold_test_preds.append(m.predict_proba(X_test_arr)[:, 1])
        oof_train[:, j] = oof
        oof_test[:, j]  = np.mean(fold_test_preds, axis=0)

        model.fit(X_train_arr, y_train)
        y_prob_l1 = model.predict_proba(X_test_arr)[:, 1]
        y_pred_l1 = model.predict(X_test_arr)
        roc_l1    = roc_auc_score(y_test, y_prob_l1)
        ap_l1     = average_precision_score(y_test, y_prob_l1)
        rep_l1    = classification_report(y_test, y_pred_l1, output_dict=True)
        layer1_results[name] = {
            'roc_auc': roc_l1, 'avg_precision': ap_l1,
            'y_prob': y_prob_l1.tolist(), 'report': rep_l1,
        }
        print(f"  {name:20s}  ROC-AUC={roc_l1:.4f}  Avg-Prec={ap_l1:.4f}")

    # ── 9. Layer-2 blender ───────────────────────────────────────────────────
    blender = GradientBoostingClassifier(
        n_estimators=100, learning_rate=0.05, max_depth=2,
        subsample=0.8, random_state=42)
    blender.fit(oof_train, y_train)

    y_prob_stack = blender.predict_proba(oof_test)[:, 1]
    y_pred_stack = blender.predict(oof_test)
    roc_stack    = roc_auc_score(y_test, y_prob_stack)
    ap_stack     = average_precision_score(y_test, y_prob_stack)
    rep_stack    = classification_report(y_test, y_pred_stack, output_dict=True)
    print(f"\n  {'Stacking Blender':20s}  ROC-AUC={roc_stack:.4f}  Avg-Prec={ap_stack:.4f}")

    # ── 10. Generate plots ───────────────────────────────────────────────────
    print("\nGenerating plots...")
    _colors = {'GradientBoosting': 'steelblue', 'ExtraTrees': 'seagreen',
               'RandomForest': 'darkorange', 'Stacking': 'crimson'}

    # ROC — all models + stacking
    fig_roc, ax = plt.subplots(figsize=(8, 5))
    for name, res in layer1_results.items():
        fpr, tpr, _ = roc_curve(y_test, res['y_prob'])
        ax.plot(fpr, tpr, label=f"{name} (AUC={res['roc_auc']:.3f})",
                color=_colors[name], linewidth=1.5, linestyle='--')
    fpr_s, tpr_s, _ = roc_curve(y_test, y_prob_stack)
    ax.plot(fpr_s, tpr_s, label=f"Stacking (AUC={roc_stack:.3f})",
            color=_colors['Stacking'], linewidth=2.5)
    ax.plot([0, 1], [0, 1], 'k--', alpha=0.3)
    ax.set_xlabel('False Positive Rate'); ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC-AUC — Stacking Ensemble vs Base Models')
    ax.legend(); ax.grid(alpha=0.3)
    img_roc = fig_to_base64(fig_roc)

    # Precision-Recall — all models + stacking
    fig_pr, ax = plt.subplots(figsize=(8, 5))
    for name, res in layer1_results.items():
        prec, rec, _ = precision_recall_curve(y_test, res['y_prob'])
        ax.plot(rec, prec, label=f"{name} (AP={res['avg_precision']:.3f})",
                color=_colors[name], linewidth=1.5, linestyle='--')
    prec_s, rec_s, _ = precision_recall_curve(y_test, y_prob_stack)
    ax.plot(rec_s, prec_s, label=f"Stacking (AP={ap_stack:.3f})",
            color=_colors['Stacking'], linewidth=2.5)
    ax.axhline(y_test.mean(), color='gray', linestyle=':',
               label=f'No-skill ({y_test.mean():.2f})')
    ax.set_xlabel('Recall'); ax.set_ylabel('Precision')
    ax.set_title('Precision-Recall — Stacking Ensemble vs Base Models')
    ax.legend(); ax.grid(alpha=0.3)
    img_pr = fig_to_base64(fig_pr)

    # Blender meta-feature importance
    fig_imp, ax = plt.subplots(figsize=(6, 3))
    pd.Series(blender.feature_importances_,
              index=list(BASE_MODELS.keys())).sort_values().plot(
        kind='barh', ax=ax, color='crimson')
    ax.set_title('Blender Feature Importance (Layer-2 GradientBoosting)')
    ax.set_xlabel('Importance'); ax.grid(axis='x', alpha=0.3)
    img_imp = fig_to_base64(fig_imp)

    # Correlation heatmap
    fig_corr, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr_matrix[FEATURE_COLS].loc[FEATURE_COLS].values,
                   cmap='RdYlGn_r', vmin=0, vmax=1)
    ax.set_xticks(range(n_features))
    ax.set_xticklabels(FEATURE_COLS, rotation=45, ha='right', fontsize=7)
    ax.set_yticks(range(n_features))
    ax.set_yticklabels(FEATURE_COLS, fontsize=7)
    plt.colorbar(im, ax=ax)
    ax.set_title('PARC — Pairwise Absolute Correlation Matrix')
    img_corr = fig_to_base64(fig_corr)

    # ── 11. Save stats JSON (consumed by build_report.py) ───────────────────
    print("\nSaving stats JSON...")

    stats = {
        'conversation_key': key,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dataset': {
            'shape': list(df.shape),
            'model_rows': len(df_model),
            'date_range': {
                'min': str(df[ts_col].min().date()),
                'max': str(df[ts_col].max().date()),
            },
            'train_samples': split_idx,
            'test_samples': len(test_df),
            'positive_rate': float(y_all.mean()),
        },
        'features': {
            'all': FEATURE_COLS,
            'parc_threshold': float(parc_threshold),
            'vif_threshold': 15,
            'details': {
                col: {
                    'vif':       float(vif[col]),
                    'parc':      float(parc[col]),
                    'decision':  decisions[col],
                    'layer':     FINANCIAL_REASONING.get(col, {}).get('layer', '—'),
                    'reasoning': FINANCIAL_REASONING.get(col, {}).get('reasoning', '—'),
                }
                for col in FEATURE_COLS
            },
            'dropped':    drop_features,
            'concerning': concern_features,
            'kept':       keep_features,
            'final':      final_features,
        },
        'models': {
            **{
                name: {
                    'roc_auc':       res['roc_auc'],
                    'avg_precision': res['avg_precision'],
                    'precision_up':  res['report'].get('1', res['report'].get(1, {})).get('precision', 0),
                    'recall_up':     res['report'].get('1', res['report'].get(1, {})).get('recall', 0),
                }
                for name, res in layer1_results.items()
            },
            'Stacking': {
                'roc_auc':       roc_stack,
                'avg_precision': ap_stack,
                'precision_up':  rep_stack.get('1', rep_stack.get(1, {})).get('precision', 0),
                'recall_up':     rep_stack.get('1', rep_stack.get(1, {})).get('recall', 0),
            },
        },
        'images': {
            'roc':         img_roc,
            'pr':          img_pr,
            'importance':  img_imp,
            'correlation': img_corr,
        },
    }

    stats_path = os.path.join(os.path.dirname(__file__), '../../../../data/gb_stats.json')
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

    print(f"\nStats saved : {stats_path}")
    print("=" * 60)
    print(f"Stacking ROC-AUC    : {roc_stack:.4f}")
    print(f"Stacking Avg-Prec   : {ap_stack:.4f}")
    print(f"Final features used : {len(final_features)}")
    print("=" * 60)
    return stats_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python train_gradient_boosting.py <conversation_key>")
        sys.exit(1)
    run_training(sys.argv[1])
