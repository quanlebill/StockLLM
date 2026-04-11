"""
build_report.py — Generate HTML report from training stats + explanation text.

Usage:
    python build_report.py gb_stats.json "Your full financial explanation here..."
    python build_report.py gb_stats.json explanation.txt   # reads from file if path exists
    python build_report.py gb_stats.json                   # explanation left blank
"""

import sys, os, json
from datetime import datetime


def build_report(stats: dict, explanation: str = "") -> str:
    """
    Build and save gb_report.html from stats dict + explanation text.

    Args:
        stats:       Output of run_training() — the gb_stats.json contents.
        explanation: Free-form financial analysis text (HTML allowed).

    Returns:
        Path to the saved HTML report.
    """
    ds   = stats['dataset']
    feat = stats['features']
    mods = stats['models']
    imgs = stats['images']

    parc_t    = feat['parc_threshold']
    vif_t     = feat['vif_threshold']
    n_feat    = len(feat['all'])

    # ── Feature table rows ────────────────────────────────────────────────────
    def badge(decision):
        colors = {'KEEP': '#28a745', 'CONCERNING': '#fd7e14', 'DROP': '#dc3545'}
        c = colors.get(decision, '#6c757d')
        return f'<span style="background:{c};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{decision}</span>'

    feature_rows = ""
    for col in feat['all']:
        d = feat['details'][col]
        vif_color  = '#dc3545' if d['vif']  > vif_t  else '#28a745'
        parc_color = '#dc3545' if d['parc'] > parc_t else '#28a745'
        feature_rows += f"""
        <tr>
          <td><b>{col}</b></td>
          <td><span style="background:#e9ecef;padding:2px 6px;border-radius:3px;font-size:11px">{d['layer']}</span></td>
          <td style="color:{vif_color};font-weight:bold">{d['vif']:.2f}</td>
          <td style="color:{parc_color};font-weight:bold">{d['parc']:.4f}</td>
          <td>{badge(d['decision'])}</td>
          <td style="font-size:12px;color:#555">{d['reasoning']}</td>
        </tr>"""

    # ── Final feature set table ───────────────────────────────────────────────
    final_feature_rows = ""
    for i, col in enumerate(feat['final'], 1):
        d = feat['details'][col]
        final_feature_rows += f"""
        <tr>
          <td>{i}</td>
          <td><b>{col}</b></td>
          <td>{d['layer']}</td>
          <td>{d['vif']:.2f}</td>
          <td>{d['parc']:.4f}</td>
        </tr>"""

    # ── Model performance cards ───────────────────────────────────────────────
    model_order  = [m for m in mods if m != 'Stacking'] + ['Stacking']
    model_colors = {
        'GradientBoosting': '#457b9d',
        'AdaBoost':         '#2a9d8f',
        'RandomForest':     '#e9a835',
        'Stacking':         '#e63946',
    }

    model_cards = ""
    for name in model_order:
        m  = mods[name]
        c  = model_colors.get(name, '#6c757d')
        highlight = 'border: 2px solid #e63946;' if name == 'Stacking' else ''
        model_cards += f"""
        <div class="card" style="{highlight}">
          <h3 style="margin-top:0;color:{c}">{name}{"&nbsp;<small style='font-size:12px;color:#888'>(blender)</small>" if name == "Stacking" else ""}</h3>
          <div class="metric-box"><div class="metric-val">{m['roc_auc']:.3f}</div><div class="metric-lbl">ROC-AUC</div></div>
          <div class="metric-box"><div class="metric-val">{m['avg_precision']:.3f}</div><div class="metric-lbl">Avg Precision</div></div>
          <div class="metric-box"><div class="metric-val">{m['precision_up']:.2f}</div><div class="metric-lbl">Precision (up)</div></div>
          <div class="metric-box"><div class="metric-val">{m['recall_up']:.2f}</div><div class="metric-lbl">Recall (up)</div></div>
        </div>"""

    # ── Explanation section ───────────────────────────────────────────────────
    explanation_html = ""
    if explanation.strip():
        # Wrap plain-text paragraphs in <p> tags if there's no HTML already
        if '<' not in explanation:
            paragraphs = [p.strip() for p in explanation.split('\n\n') if p.strip()]
            explanation_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)
        else:
            explanation_html = explanation

    explanation_section = f"""
<h2>6. Financial Interpretation</h2>
<div class="card">
  {explanation_html if explanation_html else '<p style="color:#888;font-style:italic">No explanation provided. Run: python build_report.py gb_stats.json "your analysis..."</p>'}
</div>""" if True else ""

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NVDA 1-Week Prediction — Stacking Ensemble Report</title>
<style>
  body  {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          margin: 0; padding: 20px 40px; background: #f8f9fa; color: #212529; }}
  h1    {{ color: #1a1a2e; border-bottom: 3px solid #e63946; padding-bottom: 10px; }}
  h2    {{ color: #457b9d; margin-top: 40px; border-left: 4px solid #457b9d; padding-left: 12px; }}
  h3    {{ color: #555; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
  th    {{ background: #1a1a2e; color: white; padding: 10px 12px;
           text-align: left; font-size: 13px; }}
  td    {{ padding: 9px 12px; border-bottom: 1px solid #dee2e6;
           vertical-align: top; font-size: 13px; }}
  tr:hover {{ background: #f1f3f5; }}
  .metric-box {{ display: inline-block; background: white; border-radius: 8px;
                 padding: 16px 24px; margin: 8px; text-align: center;
                 box-shadow: 0 1px 4px rgba(0,0,0,0.1); min-width: 110px; }}
  .metric-val {{ font-size: 26px; font-weight: bold; color: #e63946; }}
  .metric-lbl {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .card  {{ background: white; border-radius: 8px; padding: 20px 24px; margin: 16px 0;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  .info  {{ background: #d1ecf1; border-left: 4px solid #17a2b8;
            padding: 10px 16px; border-radius: 4px; margin: 8px 0; }}
  .warn  {{ background: #fff3cd; border-left: 4px solid #ffc107;
            padding: 10px 16px; border-radius: 4px; margin: 8px 0; }}
  img    {{ max-width: 100%; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); }}
  .grid  {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .grid4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
  footer {{ color: #888; font-size: 12px; margin-top: 40px;
            border-top: 1px solid #dee2e6; padding-top: 12px; }}
</style>
</head>
<body>

<h1>NVDA 1-Week Stock Prediction — Stacking Ensemble Report</h1>
<p style="color:#666">
  Generated: {stats['generated_at']} &nbsp;|&nbsp;
  Conversation key: <code>{stats['conversation_key']}</code><br>
  Framework: Top-Down Strategy (Macro &rarr; Sector &rarr; Stock)
</p>

<div class="info">
  <b>Architecture:</b> Layer 1 = GradientBoosting + AdaBoost + RandomForest (OOF stacking via TimeSeriesSplit).
  Layer 2 = GradientBoosting blender trained on out-of-fold meta-probabilities.
  Features selected by VIF + PARC multicollinearity filters.
  Target = forward 5-day return &gt; 0 (binary: up / down next week).
</div>

<!-- ── 1. Dataset ── -->
<h2>1. Dataset Overview</h2>
<div class="card">
  <div>
    <div class="metric-box"><div class="metric-val">{ds['model_rows']}</div><div class="metric-lbl">Model rows</div></div>
    <div class="metric-box"><div class="metric-val">{n_feat}</div><div class="metric-lbl">Initial features</div></div>
    <div class="metric-box"><div class="metric-val">{len(feat['final'])}</div><div class="metric-lbl">Final features</div></div>
    <div class="metric-box"><div class="metric-val">{int(ds['positive_rate']*100)}%</div><div class="metric-lbl">Positive rate</div></div>
    <div class="metric-box"><div class="metric-val">{ds['train_samples']}</div><div class="metric-lbl">Train samples</div></div>
    <div class="metric-box"><div class="metric-val">{ds['test_samples']}</div><div class="metric-lbl">Test samples</div></div>
  </div>
  <p style="margin-top:12px;color:#555;font-size:13px">
    Date range: {ds['date_range']['min']} to {ds['date_range']['max']}<br>
    Train/Test split is chronological — last 20% held out as test set.
  </p>
</div>

<!-- ── 2. PARC & VIF ── -->
<h2>2. PARC &amp; VIF Multicollinearity Analysis</h2>
<div class="card">
  <p>
    PARC threshold = 2 / &radic;{n_feat} = <b>{parc_t:.4f}</b> &nbsp;|&nbsp;
    VIF threshold = <b>{vif_t}</b><br>
    VIF &gt; {vif_t} AND PARC &gt; threshold &rarr;
      <span style="color:#dc3545;font-weight:bold">DROP</span> &nbsp;|&nbsp;
    VIF &gt; {vif_t} AND PARC &le; threshold &rarr;
      <span style="color:#fd7e14;font-weight:bold">CONCERNING</span> &nbsp;|&nbsp;
    else &rarr; <span style="color:#28a745;font-weight:bold">KEEP</span>
  </p>
  <p style="font-size:13px;color:#555">
    Dropped: <b>{', '.join(feat['dropped']) or 'none'}</b> &nbsp;|&nbsp;
    Concerning: <b>{', '.join(feat['concerning']) or 'none'}</b> &nbsp;|&nbsp;
    Kept: <b>{len(feat['kept'])}</b> features
  </p>
</div>

<table>
  <tr>
    <th>Feature</th><th>Layer</th><th>VIF</th><th>PARC (max)</th>
    <th>Decision</th><th>Financial Reasoning</th>
  </tr>
  {feature_rows}
</table>

<h3>Correlation Heatmap</h3>
<img src="data:image/png;base64,{imgs['correlation']}" alt="Correlation Matrix">

<!-- ── 3. Feature Selection Summary ── -->
<h2>3. Final Feature Set ({len(feat['final'])} features)</h2>
<table>
  <tr><th>#</th><th>Feature</th><th>Layer</th><th>VIF</th><th>PARC</th></tr>
  {final_feature_rows}
</table>

<!-- ── 4. Model Performance ── -->
<h2>4. Model Performance</h2>
<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px">
  {model_cards}
</div>

<div class="grid" style="margin-top:20px">
  <div><img src="data:image/png;base64,{imgs['roc']}" alt="ROC Curve"></div>
  <div><img src="data:image/png;base64,{imgs['pr']}" alt="Precision-Recall Curve"></div>
</div>

<!-- ── 5. Blender Importance ── -->
<h2>5. Blender Meta-Feature Importance</h2>
<img src="data:image/png;base64,{imgs['importance']}" alt="Blender Importance">

<!-- ── 6. Financial Interpretation ── -->
{explanation_section}

<footer>
  Model: Stacking Ensemble (GB + AdaBoost + RF | GB blender).<br>
  Feature selection: VIF threshold={vif_t}, PARC threshold=2/&radic;n={parc_t:.4f}.<br>
  Framework: Top-Down Strategy (Macro &rarr; Sector &rarr; Stock Scan).
</footer>
</body>
</html>"""

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gb_report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report saved: {report_path}")
    return report_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_report.py <gb_stats.json> [explanation_text_or_file]")
        sys.exit(1)

    stats_path = sys.argv[1]
    with open(stats_path, 'r', encoding='utf-8') as f:
        stats_data = json.load(f)

    explanation_arg = ""
    if len(sys.argv) >= 3:
        raw = sys.argv[2]
        # If it looks like a file path that exists, read it; otherwise treat as inline text
        if os.path.isfile(raw):
            with open(raw, 'r', encoding='utf-8') as f:
                explanation_arg = f.read()
        else:
            explanation_arg = raw

    build_report(stats_data, explanation_arg)
