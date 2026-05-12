# app.py
# The Streamlit web interface for sec-fundamental-analyst.
#
# How to run:
#   1. Get a free Groq API key at https://console.groq.com/ (no credit card needed)
#   2. Create a .env file in this folder containing: GROQ_API_KEY=your_key_here
#   3. In your terminal: python -m streamlit run app.py
#   4. A browser tab opens automatically at http://localhost:8501

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from groq import Groq
from dotenv import load_dotenv

from edgar_fetcher import get_company_cik, get_company_info, search_companies_by_name, _load_company_tickers
from financial_extractor import build_financials_dataframe
from analyser import (
    calculate_ratios, flag_ratio, format_value,
    calculate_confidence_score, find_data_gaps, THRESHOLDS,
)
from peer_fetcher import fetch_peer_ratios
from valuation_fetcher import (
    fetch_valuation_metrics, format_valuation_value,
    VALUATION_METRICS, VALUATION_CONTEXT, VALUATION_TYPICAL,
)

load_dotenv()


# ── THEME ─────────────────────────────────────────────────────────────────────
# Inject custom CSS to give the app an investment-bank white look.
# st.markdown with unsafe_allow_html=True lets us drop raw HTML/CSS into the page.

st.set_page_config(
    page_title="SEC Fundamental Analyst",
    layout="wide",
)

st.markdown("""
<style>
    /* Clean white canvas */
    .main .block-container { max-width: 1100px; padding-top: 2rem; padding-bottom: 3rem; }
    #MainMenu, footer, header { visibility: hidden; }

    /* Section headings */
    .section-heading {
        color: #1a237e;
        font-size: 1rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        border-bottom: 2px solid #e8eaf6;
        padding-bottom: 6px;
        margin-top: 36px;
        margin-bottom: 16px;
    }

    /* Verdict banner */
    .verdict-strong   { background:#e8f5e9; border-left:5px solid #2e7d32; padding:18px 22px; border-radius:4px; margin:16px 0; }
    .verdict-moderate { background:#fff8e1; border-left:5px solid #f9a825; padding:18px 22px; border-radius:4px; margin:16px 0; }
    .verdict-weak     { background:#ffebee; border-left:5px solid #c62828; padding:18px 22px; border-radius:4px; margin:16px 0; }
    .verdict-label    { font-size:1.5rem; font-weight:800; margin:0 0 4px 0; }
    .verdict-sub      { font-size:0.9rem; color:#555; margin:0; }

    /* Ratio metric cards */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 18px 12px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .metric-label { font-size:0.72rem; color:#888; text-transform:uppercase; letter-spacing:0.07em; margin-bottom:8px; }
    .metric-value { font-size:1.55rem; font-weight:700; color:#1a237e; margin-bottom:10px; }
    .badge-strong   { display:inline-block; background:#e8f5e9; color:#2e7d32; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; }
    .badge-moderate { display:inline-block; background:#fff8e1; color:#f57f17; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; }
    .badge-weak     { display:inline-block; background:#ffebee; color:#c62828; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; }
    .badge-na       { display:inline-block; background:#f5f5f5; color:#9e9e9e; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; }

    /* Analyst notes box */
    .notes-box {
        background:#f9f9fb;
        border:1px solid #e0e0e0;
        border-radius:8px;
        padding:24px 28px;
        line-height:1.8;
        font-size:0.95rem;
        color:#2c2c2c;
    }

    /* Footer */
    .app-footer {
        margin-top:48px;
        padding-top:14px;
        border-top:1px solid #e0e0e0;
        color:#aaa;
        font-size:0.78rem;
        text-align:center;
    }
</style>
""", unsafe_allow_html=True)


# ── HEADER ────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="border-bottom:3px solid #1a237e; padding-bottom:16px; margin-bottom:28px;">
    <h1 style="color:#1a237e; font-size:1.9rem; font-weight:800; margin:0;">
        SEC Fundamental Analyst
    </h1>
    <p style="color:#666; font-size:0.9rem; margin:6px 0 0 0;">
        Instant fundamental analysis from official SEC filings — ratios, trends, and AI insights in seconds.
    </p>
</div>
""", unsafe_allow_html=True)


# ── UI HELPERS ────────────────────────────────────────────────────────────────

def render_verdict_banner(verdict, strong, total):
    colour_map = {"STRONG": "#2e7d32", "MODERATE": "#f57f17", "WEAK": "#c62828"}
    css_class  = f"verdict-{verdict.lower()}"
    colour     = colour_map[verdict]
    return f"""
    <div class="{css_class}">
        <p class="verdict-label" style="color:{colour};">{verdict}</p>
        <p class="verdict-sub">{strong} of {total} metrics rated Strong</p>
    </div>"""


def render_metric_card(label, value, flag):
    badge_class = f"badge-{flag.lower().replace('/', '')}"  # "N/A" → "badge-na"
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <span class="{badge_class}">{flag}</span>
    </div>"""


def show_ratio_cards(ratios):
    """Display all 6 ratios as cards, two rows of 3."""
    items = list(ratios.items())
    for row_start in range(0, len(items), 3):
        cols = st.columns(3, gap="small")
        for i, col in enumerate(cols):
            idx = row_start + i
            if idx < len(items):
                name, value = items[idx]
                with col:
                    st.markdown(
                        render_metric_card(
                            name.replace("_", " ").title(),
                            format_value(name, value),
                            flag_ratio(name, value),
                        ),
                        unsafe_allow_html=True,
                    )
        st.markdown("<br>", unsafe_allow_html=True)


def show_threshold_legend():
    """
    Expandable table showing the exact numeric thresholds that define
    Strong / Moderate / Weak for each of the 6 financial ratios.
    Makes the rating system transparent and trustworthy for users.
    """
    LABELS = {
        "operating_margin":  "Operating Margin",
        "net_profit_margin": "Net Profit Margin",
        "revenue_growth":    "Revenue Growth",
        "debt_to_equity":    "Debt / Equity",
        "current_ratio":     "Current Ratio",
        "return_on_equity":  "Return on Equity",
    }
    # Metrics where lower is better (strong threshold is the LOWER number)
    INVERTED    = {"debt_to_equity"}
    # Metrics that display as "x" multiples rather than percentages
    RATIO_STYLE = {"debt_to_equity", "current_ratio"}

    rows_html = ""
    for key, t in THRESHOLDS.items():
        label  = LABELS[key]
        s, m   = t["strong"], t["moderate"]

        # Format threshold values to match how the metric cards display them
        s_fmt = f"{s:.2f}x" if key in RATIO_STYLE else f"{s*100:.0f}%"
        m_fmt = f"{m:.2f}x" if key in RATIO_STYLE else f"{m*100:.0f}%"

        if key in INVERTED:
            # Debt/Equity: lower is better, so the ranges are flipped
            strong_rng   = f"< {s_fmt}"
            moderate_rng = f"{s_fmt} – {m_fmt}"
            weak_rng     = f"> {m_fmt}"
        else:
            strong_rng   = f"> {s_fmt}"
            moderate_rng = f"{m_fmt} – {s_fmt}"
            weak_rng     = f"< {m_fmt}"

        rows_html += (
            f"<tr>"
            f"<td style='padding:7px 12px;font-weight:600;color:#37474f;"
            f"border-bottom:1px solid #f0f0f0'>{label}</td>"
            f"<td style='padding:7px 12px;text-align:center;color:#2e7d32;"
            f"background:#f1f8e9;border-bottom:1px solid #f0f0f0'>{strong_rng}</td>"
            f"<td style='padding:7px 12px;text-align:center;color:#f57f17;"
            f"background:#fffde7;border-bottom:1px solid #f0f0f0'>{moderate_rng}</td>"
            f"<td style='padding:7px 12px;text-align:center;color:#c62828;"
            f"background:#fff8f8;border-bottom:1px solid #f0f0f0'>{weak_rng}</td>"
            f"</tr>"
        )

    with st.expander("How are Strong / Moderate / Weak ratings calculated?  (click to expand)"):
        st.markdown(f"""
        <table style='width:100%;border-collapse:collapse;font-size:0.88rem;margin-top:4px;'>
          <thead>
            <tr style='background:#f5f5f5;'>
              <th style='padding:8px 12px;text-align:left;color:#37474f;'>Metric</th>
              <th style='padding:8px 12px;text-align:center;color:#2e7d32;'>Strong</th>
              <th style='padding:8px 12px;text-align:center;color:#f57f17;'>Moderate</th>
              <th style='padding:8px 12px;text-align:center;color:#c62828;'>Weak</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style='font-size:0.75rem;color:#9e9e9e;margin-top:10px;'>
          These are sector-agnostic benchmarks used as general screening rules.
          To adjust them for your own criteria, edit
          <code>src/analyser.py &rarr; THRESHOLDS</code>.
        </p>
        """, unsafe_allow_html=True)


def render_valuation_card(label, value, typical_range):
    """Single valuation metric card — same visual style as ratio cards, but no badge."""
    # Only show the "Typical:" hint if the metric has one (market_cap does not)
    typical_html = (
        f"<div style='font-size:0.65rem;color:#9e9e9e;margin-top:8px;'>{typical_range}</div>"
        if typical_range else "<div style='margin-top:16px;'></div>"
    )
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {typical_html}
    </div>"""


def show_valuation_cards(val_data):
    """
    Display the 5 valuation metric cards plus an expandable explanation footnote.
    val_data: dict returned by fetch_valuation_metrics(), or None if unavailable.
    """
    val_keys    = list(VALUATION_METRICS.keys())     # ["market_cap", "trailing_pe", ...]
    val_labels  = {k: v[1] for k, v in VALUATION_METRICS.items()}  # key → display label

    # Row 1: market_cap · trailing_pe · forward_pe
    cols1 = st.columns(3, gap="small")
    for i, col in enumerate(cols1):
        key = val_keys[i]
        raw = (val_data or {}).get(key)
        with col:
            st.markdown(
                render_valuation_card(
                    val_labels[key],
                    format_valuation_value(key, raw),
                    VALUATION_TYPICAL[key],
                ),
                unsafe_allow_html=True,
            )
    st.markdown("<br>", unsafe_allow_html=True)

    # Row 2: ev_ebitda · price_to_book · (empty placeholder column)
    cols2 = st.columns(3, gap="small")
    for i in range(2):
        key = val_keys[3 + i]
        raw = (val_data or {}).get(key)
        with cols2[i]:
            st.markdown(
                render_valuation_card(
                    val_labels[key],
                    format_valuation_value(key, raw),
                    VALUATION_TYPICAL[key],
                ),
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Expandable footnote — click to reveal full explanations + normal ranges
    with st.expander("What do these valuation metrics mean?  (click to expand)"):
        for key, ctx in VALUATION_CONTEXT.items():
            st.markdown(f"**{ctx['label']}**")
            st.markdown(f"{ctx['what']}")
            st.caption(f"Normal range — {ctx['range']}")
            st.markdown("---")


def render_peer_search_widget(peer_num):
    """
    A self-contained company search widget for one peer slot.
    Accepts a company name OR ticker — mirrors the main search bar exactly.
    Stores its state in session_state so results survive Streamlit reruns.
    Returns the confirmed company dict {"ticker", "cik", "title"} or None.
    """
    prefix = f"peer{peer_num}"   # "peer1" or "peer2" — used to namespace all state keys

    # ── Input row: text box + Search button side by side ──────────────────────
    col_input, col_btn = st.columns([4, 1], gap="small")
    with col_input:
        query = st.text_input(
            f"Peer {peer_num} — company name or ticker",
            placeholder="e.g.  MA  or  Mastercard",
            key=f"{prefix}_input",
        )
    with col_btn:
        # Vertical spacer so the button lines up with the text input
        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
        searched = st.button("Search", key=f"{prefix}_btn", use_container_width=True)

    # ── Run the EDGAR search when the Search button is clicked ────────────────
    if searched and query.strip():
        # Clear any previous results for this peer slot before searching again
        st.session_state[f"{prefix}_matches"]   = []
        st.session_state[f"{prefix}_confirmed"] = None

        with st.spinner(f"Searching EDGAR..."):
            tickers_data = _load_company_tickers()
            cik, title   = get_company_info(query.strip().upper(), _data=tickers_data)

        if cik:
            # Exact ticker match — confirm immediately, no dropdown needed
            st.session_state[f"{prefix}_confirmed"] = {
                "ticker": query.strip().upper(),
                "cik":    cik,
                "title":  title,
            }
        else:
            matches = search_companies_by_name(query.strip(), _data=tickers_data)
            if not matches:
                st.warning(
                    f"No companies found for **'{query.strip()}'**. "
                    "Try the stock ticker symbol (e.g. **MA** for Mastercard)."
                )
            elif len(matches) == 1:
                # Only one result — confirm it automatically
                st.session_state[f"{prefix}_confirmed"] = matches[0]
            else:
                # Multiple results — store them and show a dropdown below
                st.session_state[f"{prefix}_matches"] = matches

    # ── Dropdown (only shown when multiple matches and nothing confirmed yet) ──
    matches   = st.session_state.get(f"{prefix}_matches", [])
    confirmed = st.session_state.get(f"{prefix}_confirmed")

    if matches and not confirmed:
        options = {f"{m['title']}  ({m['ticker']})": m for m in matches}
        choice  = st.selectbox(
            f"Found {len(matches)} companies — select one:",
            list(options.keys()),
            key=f"{prefix}_select",
        )
        if st.button("Confirm selection →", key=f"{prefix}_confirm", type="primary"):
            st.session_state[f"{prefix}_confirmed"] = options[choice]
            st.session_state[f"{prefix}_matches"]   = []
            st.rerun()   # re-render the widget showing the confirmed chip

    # ── Confirmed chip — shows the selected company with a Clear button ────────
    confirmed = st.session_state.get(f"{prefix}_confirmed")
    if confirmed:
        col_chip, col_clear = st.columns([6, 1])
        with col_chip:
            st.markdown(
                f"<div style='background:#e8f5e9;border-left:3px solid #2e7d32;"
                f"padding:8px 14px;border-radius:4px;font-size:0.88rem;color:#1b5e20;'>"
                f"<strong>{confirmed['title']}</strong>"
                f"&nbsp;<span style='color:#555;font-weight:400'>({confirmed['ticker']})</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with col_clear:
            st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
            if st.button("Clear", key=f"{prefix}_clear"):
                st.session_state[f"{prefix}_confirmed"] = None
                st.session_state[f"{prefix}_matches"]   = []
                st.rerun()

    return st.session_state.get(f"{prefix}_confirmed")


def render_peer_comparison_table(companies):
    """
    Build a colour-coded HTML comparison table.

    companies: list of dicts, each shaped like:
        {"ticker": "MA", "company_name": "Mastercard Inc.", "ratios": {...}}

    For each metric row: the best value is highlighted green, the worst red.
    For Debt/Equity specifically, lower is better (inverted logic).
    """
    RATIO_LABELS = {
        "operating_margin":  "Operating Margin",
        "net_profit_margin": "Net Profit Margin",
        "revenue_growth":    "Revenue Growth",
        "debt_to_equity":    "Debt / Equity",
        "current_ratio":     "Current Ratio",
        "return_on_equity":  "Return on Equity",
    }
    # For these metrics, a LOWER number is better (inverted from the rest)
    INVERTED = {"debt_to_equity"}

    # ── Header row ────────────────────────────────────────────────────────────
    header_cells = "<th style='text-align:left;padding:10px 14px;'>Metric</th>"
    for c in companies:
        header_cells += (
            f"<th style='text-align:center;padding:10px 14px;'>"
            f"{c['company_name']}<br>"
            f"<span style='font-weight:400;color:#c5cae9;font-size:0.75rem'>"
            f"{c['ticker'].upper()}</span></th>"
        )

    # ── Data rows ─────────────────────────────────────────────────────────────
    rows_html = ""
    for metric, label in RATIO_LABELS.items():
        # Pull the raw numeric value for this metric from every company
        values = [c["ratios"].get(metric) for c in companies]

        # Find valid (non-None, non-NaN) values to determine best and worst.
        # The trick "v == v" is False ONLY for NaN (NaN is never equal to itself
        # in standard floating-point maths — it's a quirk of the IEEE standard).
        # Think of it as: "is this a real number, not a blank?"
        valid = [(i, v) for i, v in enumerate(values)
                 if v is not None and v == v]

        # Determine which index is the best and which is the worst
        if len(valid) >= 2:
            ordered   = sorted(valid, key=lambda pair: pair[1])  # ascending by value
            min_val   = ordered[0][1]
            max_val   = ordered[-1][1]

            if min_val == max_val:
                # All companies tied — no colouring
                best_idx = worst_idx = None
            elif metric in INVERTED:
                best_idx  = ordered[0][0]   # lowest value wins (less debt is better)
                worst_idx = ordered[-1][0]  # highest value loses
            else:
                best_idx  = ordered[-1][0]  # highest value wins
                worst_idx = ordered[0][0]   # lowest value loses
        else:
            best_idx = worst_idx = None

        # Build one table cell per company for this metric row
        cells = (
            f"<td style='padding:10px 14px;font-weight:600;color:#37474f;"
            f"border-bottom:1px solid #e0e0e0'>{label}</td>"
        )
        for i, val in enumerate(values):
            formatted = format_value(metric, val)

            if best_idx is not None and i == best_idx:
                bg, fg, fw = "#e8f5e9", "#2e7d32", "700"
            elif worst_idx is not None and i == worst_idx:
                bg, fg, fw = "#ffebee", "#c62828", "700"
            elif val is None or val != val:   # NaN cell
                bg, fg, fw = "#fafafa", "#bdbdbd", "400"
            else:
                bg, fg, fw = "#ffffff", "#2c2c2c", "400"

            cells += (
                f"<td style='text-align:center;padding:10px 14px;"
                f"background:{bg};color:{fg};font-weight:{fw};"
                f"border-bottom:1px solid #e0e0e0'>{formatted}</td>"
            )

        rows_html += f"<tr>{cells}</tr>\n"

    # ── Valuation section (appended below fundamentals if data is present) ────
    # Check whether at least one company has valuation data attached
    has_valuation = any(c.get("valuation") for c in companies)

    if has_valuation:
        n_cols = len(companies) + 1   # 1 label column + 1 per company

        # Section divider row — a coloured banner separating the two blocks
        rows_html += (
            f"<tr><td colspan='{n_cols}' style='background:#e8eaf6;color:#3949ab;"
            f"font-size:0.72rem;font-weight:700;padding:6px 14px;"
            f"text-transform:uppercase;letter-spacing:0.06em;'>"
            f"Valuation &nbsp;·&nbsp; Yahoo Finance · Market Data</td></tr>\n"
        )

        # Metrics where a LOWER value signals a cheaper / better-value stock
        VAL_INVERTED   = {"trailing_pe", "forward_pe", "ev_ebitda", "price_to_book"}
        # Market cap is pure size — no "good/bad" coloring
        VAL_NO_COLOR   = {"market_cap"}

        val_labels = {k: v[1] for k, v in VALUATION_METRICS.items()}

        for key, label in val_labels.items():
            # Pull the raw value for this metric from every company's valuation dict
            values = [(c.get("valuation") or {}).get(key) for c in companies]

            # Only positive values are meaningful for best/worst valuation comparison.
            # A negative P/E (loss-making company) shouldn't win the "cheapest" award.
            if key not in VAL_NO_COLOR:
                valid = [(i, v) for i, v in enumerate(values)
                         if v is not None and v == v and v > 0]
            else:
                valid = []   # market cap — skip coloring entirely

            if len(valid) >= 2:
                ordered = sorted(valid, key=lambda p: p[1])
                if ordered[0][1] == ordered[-1][1]:
                    best_idx = worst_idx = None
                elif key in VAL_INVERTED:
                    best_idx  = ordered[0][0]   # lowest multiple = cheapest = green
                    worst_idx = ordered[-1][0]  # highest multiple = priciest = red
                else:
                    best_idx  = ordered[-1][0]
                    worst_idx = ordered[0][0]
            else:
                best_idx = worst_idx = None

            cells = (
                f"<td style='padding:10px 14px;font-weight:600;color:#37474f;"
                f"border-bottom:1px solid #e0e0e0'>{label}</td>"
            )
            for i, val in enumerate(values):
                formatted = format_valuation_value(key, val)

                if best_idx is not None and i == best_idx:
                    bg, fg, fw = "#e8f5e9", "#2e7d32", "700"
                elif worst_idx is not None and i == worst_idx:
                    bg, fg, fw = "#ffebee", "#c62828", "700"
                elif val is None or val != val:
                    bg, fg, fw = "#fafafa", "#bdbdbd", "400"
                else:
                    bg, fg, fw = "#ffffff", "#2c2c2c", "400"

                cells += (
                    f"<td style='text-align:center;padding:10px 14px;"
                    f"background:{bg};color:{fg};font-weight:{fw};"
                    f"border-bottom:1px solid #e0e0e0'>{formatted}</td>"
                )
            rows_html += f"<tr>{cells}</tr>\n"

    return f"""
    <div style="overflow-x:auto;margin-top:12px;">
      <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
        <thead>
          <tr style="background:#1a237e;color:white;">{header_cells}</tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="font-size:0.75rem;color:#9e9e9e;margin-top:8px;">
        Green&nbsp;=&nbsp;best&nbsp;&nbsp;·&nbsp;&nbsp;Red&nbsp;=&nbsp;worst
        &nbsp;&nbsp;·&nbsp;&nbsp;
        Fundamentals: SEC EDGAR (primary) / Yahoo Finance (peers)
        &nbsp;·&nbsp; Valuation: Yahoo Finance · Market Data
      </p>
    </div>"""


def show_revenue_chart(df):
    """Bar chart of 5-year revenue, oldest year on the left."""
    chart_df = df[["revenue"]].copy()
    chart_df["revenue"] = (chart_df["revenue"] / 1e9).round(2)
    chart_df.columns = ["Revenue (USD billions)"]
    st.bar_chart(chart_df.sort_index())


def show_margin_trend_chart(df):
    """
    Interactive Plotly multi-line chart showing three profitability metrics
    as percentages over the available fiscal years.

    Why Plotly instead of st.bar_chart / matplotlib?
    - Hover tooltips: exact values appear when you mouse over any data point
    - Legend toggling: click a line name to hide/show it
    - Zoom: drag to zoom into a specific year range
    - This is a web app — static charts belong in PDFs, not dashboards
    """
    # Sort ascending so time flows left → right on the x-axis
    chart_df = df.sort_index(ascending=True).copy()

    # Clean year labels: "2024-09-30" → "2024"
    # Using str(y)[:4] slices the first 4 characters of the date string
    years = [str(y)[:4] for y in chart_df.index]

    # Calculate each metric as a percentage for every row in the DataFrame.
    # Pandas division is element-wise — it divides each row's value automatically,
    # just like dragging a formula down a column in Excel.
    # Multiplying by 100 converts a decimal (0.42) into a percentage (42.0).
    op_margin  = (chart_df["operating_income"] / chart_df["revenue"] * 100).round(1)
    net_margin = (chart_df["net_income"]        / chart_df["revenue"] * 100).round(1)
    roe        = (chart_df["net_income"]        / chart_df["equity"]  * 100).round(1)

    # Each (name, series, colour) tuple defines one line on the chart
    LINES = [
        ("Operating Margin",  op_margin,  "#1a237e"),
        ("Net Profit Margin", net_margin, "#2e7d32"),
        ("Return on Equity",  roe,        "#e65100"),
    ]

    # go.Figure() creates a blank Plotly chart — like opening a new blank spreadsheet
    fig = go.Figure()

    for name, series, colour in LINES:
        # series.notna().any() checks if at least ONE value in this column is real.
        # If all values are NaN (data completely missing), skip this line entirely.
        if series.notna().any():
            fig.add_trace(go.Scatter(
                x    = years,
                # .where(series.notna()) keeps real values, turns NaN into None.
                # Plotly renders None as a gap in the line rather than a zero,
                # which is honest — a gap signals missing data, not a zero result.
                y    = series.where(series.notna()),
                mode = "lines+markers",   # draw both a line AND dots at each year
                name = name,
                line   = dict(color=colour, width=2.5),
                marker = dict(size=7),
                # hovertemplate controls the tooltip text on hover.
                # %{y:.1f} formats the y-value to 1 decimal place.
                # <extra></extra> removes the default trace name from the tooltip box.
                hovertemplate=f"<b>{name}</b>: %{{y:.1f}}%<extra></extra>",
            ))

    fig.update_layout(
        title = dict(
            text = "Margin & Return Trends",
            font = dict(size=14, color="#1a237e"),
            x    = 0,    # left-align the title
        ),
        xaxis = dict(
            title      = "Fiscal Year",
            tickfont   = dict(size=12),
            showgrid   = True,
            gridcolor  = "#f0f0f0",
        ),
        yaxis = dict(
            title       = "(%)",
            ticksuffix  = "%",       # appends "%" to every y-axis label automatically
            tickfont    = dict(size=12),
            showgrid    = True,
            gridcolor   = "#f0f0f0",
            zeroline    = True,
            zerolinecolor = "#e0e0e0",
        ),
        # Legend placed horizontally above the chart so it doesn't eat into plot space
        legend = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor  = "#ffffff",   # white chart area
        paper_bgcolor = "#ffffff",   # white surrounding area
        # hovermode="x unified" shows ALL lines' values in one tooltip when hovering
        # over any x position — much cleaner than separate tooltips per line
        hovermode = "x unified",
        margin    = dict(l=50, r=20, t=60, b=50),
        height    = 360,
    )

    # st.plotly_chart renders the interactive chart directly into the Streamlit page.
    # use_container_width=True makes it stretch to fill the available column width.
    st.plotly_chart(fig, use_container_width=True)


# ── LLM HELPERS ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior fundamental equity analyst at a top-tier hedge fund with 20 years of experience.
You write balanced, critical analysis — NOT press releases.

Core rules:
- Lead every argument with specific numbers from the data provided
- Give equal weight to bull and bear cases — do not favour one side
- The bear case MUST reference actual data weaknesses (e.g. rising debt, compressing margins, slowing growth, weak or missing ratios) — do not invent generic risks
- Be direct — your reader is a sophisticated investor who needs honest risk assessment, not reassurance
- Use **bold headings** exactly as specified in the prompt — no extra sections, no conclusion paragraph, no disclaimers"""


def build_analysis_prompt(company_name, ticker, ratios, df):
    # ── Section 1: Ratio table ─────────────────────────────────────────────────
    ratio_lines = "\n".join(
        f"  {n.replace('_', ' ').title()}: {format_value(n, v)}  [{flag_ratio(n, v)}]"
        for n, v in ratios.items()
    )

    # ── Section 2: Revenue trend with YoY growth rates ────────────────────────
    # Sort oldest-first so the LLM can read the trend left-to-right naturally
    sorted_years = sorted(df.index)
    revenue_lines = []
    for i, year in enumerate(sorted_years):
        rev = df.loc[year, "revenue"]
        if pd.isna(rev):
            revenue_lines.append(f"  {str(year)[:4]}: N/A")
            continue
        rev_b = rev / 1e9
        if i > 0:
            prev_rev = df.loc[sorted_years[i - 1], "revenue"]
            if pd.notna(prev_rev) and prev_rev != 0:
                pct = (rev - prev_rev) / prev_rev * 100
                # {pct:+.1f} always prints the sign: "+8.3%" or "-2.1%"
                revenue_lines.append(f"  {str(year)[:4]}: ${rev_b:.1f}B  ({pct:+.1f}% YoY)")
            else:
                revenue_lines.append(f"  {str(year)[:4]}: ${rev_b:.1f}B")
        else:
            revenue_lines.append(f"  {str(year)[:4]}: ${rev_b:.1f}B  (baseline)")

    # ── Section 3: Data quality context ───────────────────────────────────────
    confidence = calculate_confidence_score(ratios, df)
    gaps       = find_data_gaps(ratios, df)

    confidence_descriptions = {
        5: "all metrics available, 5 complete fiscal years",
        4: "minor gaps in 1–2 metrics or years",
        3: "notable gaps — some metrics unavailable",
        2: "significant gaps — several metrics or years missing",
        1: "severe gaps — analysis reliability is limited",
    }
    confidence_note = confidence_descriptions.get(confidence, "")

    gaps_block = ""
    if gaps:
        gap_lines = "\n".join(f"  - {g}" for g in gaps)
        gaps_block = f"\n\nData gaps detected (factor these into your analysis):\n{gap_lines}"

    return f"""Company: {company_name} ({ticker.upper()})

=== FINANCIAL DATA ===

Key Ratios (most recent fiscal year — [Strong] / [Moderate] / [Weak] / [N/A]):
{ratio_lines}

5-Year Revenue Trend (oldest → newest):
{chr(10).join(revenue_lines)}

Data Completeness: {confidence}/5 — {confidence_note}{gaps_block}

=== YOUR TASK ===

Write a structured fundamental analysis with EXACTLY these three bold headings:

**Bull Case**
Identify 2–3 genuine financial strengths. Quote specific numbers from the data above.
Explain WHY each strength matters in context (e.g. what it means for a company in this industry).

**Bear Case**
Identify at least 3 specific financial risks or warning signs visible in the data.
You MUST reference actual numbers — do not write generic risks.
For every metric rated [Weak], [Moderate], or [N/A], explain the investor implication.
If revenue growth is decelerating, flag it. If debt is rising, flag it. If margins are compressing, flag it.

**Overall Verdict**
One short paragraph. Name a specific investor type (value / growth / income / avoid) and state
exactly which metric(s) support that view. Be direct — do not hedge.

Use the exact bold headings above. Keep total length under 450 words."""


def stream_llama_commentary(company_name, ticker, ratios, df):
    """Generator: yields text chunks as Llama writes them, for live streaming in the UI."""
    api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    client = Groq(api_key=api_key)
    stream = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_analysis_prompt(company_name, ticker, ratios, df)},
        ],
        max_tokens=1024,
        stream=True,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text


# ── SESSION STATE SETUP ───────────────────────────────────────────────────────
# session_state survives Streamlit reruns (which happen on every button click
# or dropdown change). Without it, our search results vanish the moment the
# user interacts with the dropdown.

if "matches"            not in st.session_state: st.session_state.matches            = []
if "selected"           not in st.session_state: st.session_state.selected           = None
if "ready_to_analyse"   not in st.session_state: st.session_state.ready_to_analyse   = False
if "peer_results"       not in st.session_state: st.session_state.peer_results       = None
if "primary_valuation"  not in st.session_state: st.session_state.primary_valuation  = None
if "valuation_ticker"   not in st.session_state: st.session_state.valuation_ticker   = None
if "peer1_confirmed"    not in st.session_state: st.session_state.peer1_confirmed    = None
if "peer1_matches"      not in st.session_state: st.session_state.peer1_matches      = []
if "peer2_confirmed"    not in st.session_state: st.session_state.peer2_confirmed    = None
if "peer2_matches"      not in st.session_state: st.session_state.peer2_matches      = []
if "financials_df"      not in st.session_state: st.session_state.financials_df      = None
if "financials_cik"     not in st.session_state: st.session_state.financials_cik     = None
if "commentary_cache"   not in st.session_state: st.session_state.commentary_cache   = None
if "commentary_ticker"  not in st.session_state: st.session_state.commentary_ticker  = None
if "run_quick_search"    not in st.session_state: st.session_state.run_quick_search    = False
if "search_input_prefill" not in st.session_state: st.session_state.search_input_prefill = ""


# ── SEARCH INPUT ──────────────────────────────────────────────────────────────

# If a quick-example button was clicked, copy the prefill value into the
# widget key NOW — before the text_input widget is rendered. Streamlit forbids
# setting a widget's key after the widget has been drawn, so this must happen here.
if st.session_state.search_input_prefill:
    st.session_state.search_input_value     = st.session_state.search_input_prefill
    st.session_state.search_input_prefill   = ""

st.markdown(
    '<div class="section-heading" style="text-transform:none; letter-spacing:normal; font-size:1.05rem;">'
    'Analyse a company — enter a ticker or name</div>',
    unsafe_allow_html=True,
)

col_search, col_btn = st.columns([4, 1], gap="small")
with col_search:
    search_input = st.text_input(
        "Ticker or company name",
        placeholder="e.g.  V  or  Mastercard  or  Apple Inc.",
        label_visibility="collapsed",
        key="search_input_value",
    )
with col_btn:
    run = st.button("Analyse", type="primary", use_container_width=True)

# ── LANDING PAGE EXTRAS (hidden once analysis is running) ─────────────────────
# `not st.session_state.ready_to_analyse` is True only on the blank landing page —
# before the user has confirmed a company. Once analysis runs, all of this disappears.

if not st.session_state.ready_to_analyse:

    # ── Change 3: Quick example buttons ───────────────────────────────────────
    # st.columns([1,1,1,3]) creates 4 columns with those relative widths —
    # the 3 buttons take the left portion, the wide empty column is padding.
    st.caption("Quick examples — click to run instantly:")
    qc1, qc2, qc3, _ = st.columns([1, 1, 1, 3])

    # Each button does three things: writes the ticker into the text box's
    # session_state key, raises the run_quick_search flag, then calls st.rerun()
    # so Streamlit immediately re-runs the script with those values in place.
    with qc1:
        if st.button("Try Visa (V)", use_container_width=True):
            st.session_state.search_input_prefill = "V"
            st.session_state.run_quick_search     = True
            st.rerun()
    with qc2:
        if st.button("Try NVIDIA (NVDA)", use_container_width=True):
            st.session_state.search_input_prefill = "NVDA"
            st.session_state.run_quick_search     = True
            st.rerun()
    with qc3:
        if st.button("Try Apple (AAPL)", use_container_width=True):
            st.session_state.search_input_prefill = "AAPL"
            st.session_state.run_quick_search     = True
            st.rerun()

    # ── Change 4: Credibility banner ──────────────────────────────────────────
    # st.info() gives a big blue alert box — too loud for a trust signal.
    # A custom markdown div lets us keep it small, grey, and unobtrusive.
    st.markdown(
        "<div style='margin-top:14px; padding:10px 16px; background:#f5f5f5; "
        "border-radius:4px; color:#666; font-size:0.82rem;'>"
        "&#128274;&nbsp; Data sourced directly from <strong>SEC EDGAR</strong> — "
        "the official US regulatory database required by law for all public companies."
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Change 5: How it works ─────────────────────────────────────────────────
    # st.columns(3) divides the page into 3 equal-width vertical panels —
    # like splitting a room into three sections with imaginary walls.
    # Each `with col:` block puts its content inside that section.
    st.markdown("<div style='margin-top:32px;'>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#9e9e9e; font-size:0.78rem; font-weight:700; "
        "text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;'>"
        "How it works</p>",
        unsafe_allow_html=True,
    )

    hw1, hw2, hw3 = st.columns(3, gap="medium")
    card_style = (
        "background:#fafafa; border:1px solid #e0e0e0; border-radius:8px; "
        "padding:20px 18px; height:130px;"
    )
    with hw1:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:1.4rem; margin-bottom:8px;'>🔍</div>"
            "<div style='font-weight:700; font-size:0.88rem; color:#1a237e; margin-bottom:6px;'>Step 1 — Search</div>"
            "<div style='font-size:0.82rem; color:#666;'>Enter any US stock ticker (V) or company name (Visa Inc.).</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with hw2:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:1.4rem; margin-bottom:8px;'>📄</div>"
            "<div style='font-weight:700; font-size:0.88rem; color:#1a237e; margin-bottom:6px;'>Step 2 — Fetch</div>"
            "<div style='font-size:0.82rem; color:#666;'>We pull the latest 10-K annual filing directly from SEC EDGAR.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with hw3:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:1.4rem; margin-bottom:8px;'>📊</div>"
            "<div style='font-weight:700; font-size:0.88rem; color:#1a237e; margin-bottom:6px;'>Step 3 — Analyse</div>"
            "<div style='font-size:0.82rem; color:#666;'>Get instant ratios, 5-year trends, and AI-powered commentary.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ── SEARCH LOGIC ──────────────────────────────────────────────────────────────

# Quick-example buttons set this flag and call st.rerun(). On the next rerun,
# the Analyse button hasn't been clicked (run=False), so we promote the flag
# to run=True here before any of the guard checks below.
if st.session_state.get("run_quick_search"):
    run = True
    st.session_state.run_quick_search = False

if run and not search_input.strip():
    st.warning("Type a ticker symbol (e.g. AAPL) or a company name (e.g. Apple).")

elif run:
    # New search — clear any previous state
    st.session_state.matches           = []
    st.session_state.selected          = None
    st.session_state.ready_to_analyse  = False
    st.session_state.peer_results      = None
    st.session_state.primary_valuation = None
    st.session_state.valuation_ticker  = None
    st.session_state.peer1_confirmed   = None
    st.session_state.peer1_matches     = []
    st.session_state.peer2_confirmed   = None
    st.session_state.peer2_matches     = []
    st.session_state.financials_df     = None
    st.session_state.financials_cik    = None
    st.session_state.commentary_cache  = None
    st.session_state.commentary_ticker = None

    query = search_input.strip()

    # Download the SEC company index once, then reuse it for both ticker lookup
    # and name search — avoids making two identical HTTP requests to EDGAR.
    with st.spinner("Searching SEC EDGAR..."):
        tickers_data = _load_company_tickers()
        cik, title   = get_company_info(query.upper(), _data=tickers_data)

    if cik:
        # Exact ticker match — go straight to analysis, show full name not just ticker
        st.session_state.selected         = {"ticker": query.upper(), "cik": cik, "title": title}
        st.session_state.ready_to_analyse = True
    else:
        # Search by name — reuse the already-downloaded JSON (no second HTTP request)
        matches = search_companies_by_name(query, _data=tickers_data)

        if not matches:
            st.error(
                f"No companies found matching **'{query}'**. "
                "Try the official ticker (e.g. AAPL for Apple, GOOGL for Alphabet/Google)."
            )
        elif len(matches) == 1:
            st.session_state.selected         = matches[0]
            st.session_state.ready_to_analyse = True
        else:
            # Multiple results — store them so the dropdown stays alive across reruns
            st.session_state.matches = matches


# ── COMPANY SELECTION DROPDOWN ────────────────────────────────────────────────
# This block runs on every rerun while matches are stored in session_state,
# so the dropdown stays visible even when the user opens/scrolls it.

if st.session_state.matches and not st.session_state.ready_to_analyse:
    options = {f"{m['title']}  ({m['ticker']})": m for m in st.session_state.matches}
    choice  = st.selectbox(
        f"Found {len(st.session_state.matches)} companies — select one:",
        list(options.keys()),
    )
    if st.button("Confirm selection →", type="primary"):
        st.session_state.selected         = options[choice]
        st.session_state.ready_to_analyse = True
        st.session_state.matches          = []
        st.rerun()


# ── ANALYSIS ──────────────────────────────────────────────────────────────────
# Only runs once a company is confirmed (either by ticker match or dropdown pick).

if st.session_state.ready_to_analyse and st.session_state.selected:
    sel          = st.session_state.selected
    ticker       = sel["ticker"]
    cik          = sel["cik"]
    company_name = sel["title"]

    if st.session_state.financials_cik != cik:
        with st.spinner("Downloading 5 years of financial data from EDGAR..."):
            df = build_financials_dataframe(cik)
        st.session_state.financials_df  = df
        st.session_state.financials_cik = cik
    else:
        df = st.session_state.financials_df

    if df is None or df.empty:
        st.error(
            f"**No financial data found for {company_name} ({ticker}).**  \n"
            "SEC EDGAR has this company in its index but returned no usable 10-K "
            "financial statements. This usually means the company is a foreign private "
            "issuer, a very recently listed company, or does not file standard US GAAP "
            "10-K reports.  \n\nTry a major US-listed company such as **AAPL**, **MSFT**, "
            "**JPM**, or **V**."
        )
        st.stop()

    ratios  = calculate_ratios(df)
    flags   = [flag_ratio(n, v) for n, v in ratios.items()]
    strong  = flags.count("Strong")
    total   = len(flags)
    verdict = "STRONG" if strong >= 5 else "MODERATE" if strong >= 3 else "WEAK"

    data_as_of = df.index[0]   # the most recent fiscal year-end date, e.g. "2024-09-30"

    st.markdown(f"""
    <div style="margin-top:8px;">
        <h2 style="color:#1a237e; font-size:1.5rem; font-weight:800; margin-bottom:4px;">
            {company_name} &nbsp;<span style="color:#888; font-weight:400; font-size:1rem;">({ticker})</span>
        </h2>
        <p style="color:#9e9e9e; font-size:0.8rem; margin:2px 0 0 0;">
            &#128197; Data as of {data_as_of} &nbsp;·&nbsp; Most recent 5 annual filings from SEC EDGAR
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-heading">Overall Verdict</div>', unsafe_allow_html=True)
    st.markdown(render_verdict_banner(verdict, strong, total), unsafe_allow_html=True)

    st.markdown('<div class="section-heading">Ratio Analysis</div>', unsafe_allow_html=True)
    show_ratio_cards(ratios)
    show_threshold_legend()

    # Fetch valuation data once per company (cache in session_state to avoid
    # re-fetching on every Streamlit rerun triggered by user interaction)
    if st.session_state.valuation_ticker != ticker:
        with st.spinner("Fetching live valuation data from Yahoo Finance..."):
            st.session_state.primary_valuation = fetch_valuation_metrics(ticker)
            st.session_state.valuation_ticker  = ticker

    st.markdown('<div class="section-heading">Valuation</div>', unsafe_allow_html=True)
    if st.session_state.primary_valuation is None:
        st.caption("Valuation data unavailable from Yahoo Finance for this ticker.")
    else:
        show_valuation_cards(st.session_state.primary_valuation)

    st.markdown('<div class="section-heading">5-Year Revenue Trend</div>', unsafe_allow_html=True)
    show_revenue_chart(df)

    st.markdown('<div class="section-heading">Margin & Return Trends</div>', unsafe_allow_html=True)
    show_margin_trend_chart(df)

    st.markdown('<div class="section-heading">5-Year Financial Summary (USD billions)</div>', unsafe_allow_html=True)
    display_df = df.copy()
    usd_cols = ["revenue","net_income","operating_income","long_term_debt","current_assets","current_liabilities","equity"]
    display_df[usd_cols] = (display_df[usd_cols] / 1_000_000_000).round(2)
    display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
    st.dataframe(display_df, use_container_width=True, height=215)

    st.markdown('<div class="section-heading">Analyst\'s Notes</div>', unsafe_allow_html=True)

    # ── Confidence badge ───────────────────────────────────────────────────────
    # Calculated entirely in Python — never trust the LLM to rate its own data quality.
    confidence = calculate_confidence_score(ratios, df)
    gaps       = find_data_gaps(ratios, df)

    if confidence >= 4:
        badge_bg, badge_fg = "#e8f5e9", "#2e7d32"
    elif confidence >= 3:
        badge_bg, badge_fg = "#fff8e1", "#f57f17"
    else:
        badge_bg, badge_fg = "#ffebee", "#c62828"

    gap_summary = f" — {len(gaps)} data gap(s) detected" if gaps else " — Complete data"

    st.markdown(f"""
    <div style="background:{badge_bg};border-left:4px solid {badge_fg};
        padding:10px 16px;border-radius:4px;margin-bottom:10px;font-size:0.85rem;">
      <strong style="color:{badge_fg};">Data confidence: {confidence}/5</strong>{gap_summary}
    </div>""", unsafe_allow_html=True)

    if gaps:
        with st.expander("View data gaps"):
            for g in gaps:
                st.caption(f"• {g}")

    # ── AI commentary (streamed once, then cached) ────────────────────────────
    # st.write_stream re-executes on every Streamlit rerun (every button click).
    # We cache the result so subsequent interactions (Compare, Clear, etc.)
    # don't burn Groq API quota or make the user wait through the stream again.
    with st.container(border=True):
        # Re-generate if: different company, or cache is None/empty (st.write_stream
        # can return None if the stream produces no output — treat that as a miss).
        needs_generation = (
            st.session_state.commentary_ticker != ticker
            or not st.session_state.commentary_cache
        )
        if needs_generation:
            try:
                result = st.write_stream(
                    stream_llama_commentary(company_name, ticker, ratios, df)
                )
                # Coerce None → "" so st.markdown never receives None
                st.session_state.commentary_cache  = result or ""
                st.session_state.commentary_ticker = ticker
            except Exception as e:
                if "api_key" in str(e).lower() or "auth" in str(e).lower():
                    st.error("GROQ_API_KEY missing or invalid — check your .env file.")
                else:
                    st.error(f"Groq error: {e}")
        else:
            st.markdown(st.session_state.commentary_cache or "")

    # ── PEER COMPARISON ───────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Peer Comparison</div>', unsafe_allow_html=True)
    st.caption("Search by company name or ticker — same as the main search bar above.")

    render_peer_search_widget(1)
    render_peer_search_widget(2)

    peer1_confirmed = st.session_state.get("peer1_confirmed")
    peer2_confirmed = st.session_state.get("peer2_confirmed")

    if st.button("Compare Peers →", type="secondary"):
        confirmed_peers = [p for p in [peer1_confirmed, peer2_confirmed] if p]

        if not confirmed_peers:
            st.warning("Search and select at least one peer above, then click Compare.")
        else:
            # Primary company uses EDGAR ratios already calculated above
            companies = [{
                "ticker":       ticker,
                "company_name": company_name,
                "ratios":       ratios,
                "valuation":    st.session_state.primary_valuation,
            }]

            with st.spinner("Fetching peer data from SEC EDGAR and Yahoo Finance..."):
                for peer in confirmed_peers:
                    peer_added = False

                    # ── Try EDGAR first (same pipeline as primary company) ──────
                    try:
                        peer_df = build_financials_dataframe(peer["cik"])
                    except Exception:
                        peer_df = pd.DataFrame()   # treat any network/parse error as "no data"

                    if not peer_df.empty:
                        try:
                            peer_ratios = calculate_ratios(peer_df)
                        except Exception:
                            peer_ratios = {k: float("nan") for k in ratios}
                        companies.append({
                            "ticker":       peer["ticker"],
                            "company_name": peer["title"],
                            "ratios":       peer_ratios,
                            "valuation":    fetch_valuation_metrics(peer["ticker"]),
                        })
                        peer_added = True

                    # ── Fall back to yfinance if EDGAR had no data ─────────────
                    if not peer_added:
                        peer_data = fetch_peer_ratios(peer["ticker"])
                        if peer_data:
                            peer_data["company_name"] = peer["title"]
                            peer_data["valuation"]    = fetch_valuation_metrics(peer["ticker"])
                            companies.append(peer_data)
                            peer_added = True

                    if not peer_added:
                        st.warning(
                            f"Could not fetch data for **{peer['title']} ({peer['ticker']})** "
                            "from either SEC EDGAR or Yahoo Finance."
                        )

            st.session_state.peer_results = companies

    # Render the comparison table — needs at least 2 companies to be meaningful
    if st.session_state.peer_results is not None:
        if len(st.session_state.peer_results) >= 2:
            st.markdown(
                render_peer_comparison_table(st.session_state.peer_results),
                unsafe_allow_html=True,
            )
        else:
            st.warning(
                "Could not fetch peer financial data from SEC EDGAR. "
                "This sometimes happens for very large financial conglomerates that use "
                "non-standard GAAP tags. Try searching by ticker symbol directly "
                "(e.g. **MS** for Morgan Stanley, **BAC** for Bank of America)."
            )

    st.markdown(
        '<div class="app-footer">Data: SEC EDGAR (public API) &nbsp;·&nbsp; '
        'AI: Llama 3.1 via Groq &nbsp;·&nbsp; Not financial advice.</div>',
        unsafe_allow_html=True,
    )
