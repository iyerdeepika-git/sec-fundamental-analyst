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
from groq import Groq
from dotenv import load_dotenv

from edgar_fetcher import get_company_cik, search_companies_by_name
from financial_extractor import build_financials_dataframe
from analyser import calculate_ratios, flag_ratio, format_value

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
        Real financial data from SEC EDGAR · AI commentary by Llama 3.1 · Free to use
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
    badge_class = f"badge-{flag.lower()}"
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


def show_revenue_chart(df):
    """Bar chart of 5-year revenue, oldest year on the left."""
    chart_df = df[["revenue"]].copy()
    chart_df["revenue"] = (chart_df["revenue"] / 1e9).round(2)
    chart_df.columns = ["Revenue (USD billions)"]
    st.bar_chart(chart_df.sort_index())


# ── LLM HELPERS ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior fundamental equity analyst with 20 years of experience.
You specialise in analysing publicly traded companies using SEC EDGAR financial data.
Write in plain English. Use the specific numbers provided. No disclaimers, no padding.
Structure your response with short bold headings."""


def build_analysis_prompt(company_name, ticker, ratios, df):
    ratio_lines = [
        f"  {n.replace('_',' ').title()}: {format_value(n,v)}  [{flag_ratio(n,v)}]"
        for n, v in ratios.items()
    ]
    revenue_trend = ", ".join(
        f"{idx}: ${df.loc[idx,'revenue']/1e9:.1f}B" for idx in df.index
    )
    return f"""Company: {company_name} ({ticker.upper()})

Key Financial Ratios (most recent fiscal year):
{chr(10).join(ratio_lines)}

5-Year Revenue Trend: {revenue_trend}

Write a concise fundamental analysis covering:
1. Business quality — operating margins and profitability
2. Financial health — balance sheet strength and debt load
3. Growth trajectory — revenue momentum and sustainability
4. Overall investment merit — would a value investor be interested?

Be direct, use the specific numbers above, and keep it under 400 words."""


def stream_llama_commentary(company_name, ticker, ratios, df):
    """Generator: yields text chunks as Llama writes them, for live streaming in the UI."""
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
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


# ── SEARCH INPUT ──────────────────────────────────────────────────────────────

st.markdown('<div class="section-heading">Search</div>', unsafe_allow_html=True)

col_search, col_btn = st.columns([4, 1], gap="small")
with col_search:
    search_input = st.text_input(
        "Ticker or company name",
        placeholder="e.g.  V  or  Mastercard  or  Apple Inc.",
        label_visibility="collapsed",
    )
with col_btn:
    run = st.button("Analyse", type="primary", use_container_width=True)


# ── SEARCH LOGIC ──────────────────────────────────────────────────────────────
# If the user types something short and uppercase-ish, treat it as a ticker.
# Otherwise, search by company name and let them pick from the results.

if run and not search_input.strip():
    st.warning("Type a ticker symbol (e.g. AAPL) or a company name (e.g. Apple).")

elif run:
    query  = search_input.strip()
    ticker = None
    cik    = None
    company_name = query

    # Heuristic: tickers are 1-5 chars and contain no spaces
    looks_like_ticker = len(query) <= 5 and " " not in query

    if looks_like_ticker:
        with st.spinner(f"Looking up {query.upper()} on SEC EDGAR..."):
            cik = get_company_cik(query.upper())
        ticker       = query.upper()
        company_name = query.upper()
    else:
        # Search by name and ask the user to confirm if multiple matches found
        with st.spinner(f"Searching SEC EDGAR for '{query}'..."):
            matches = search_companies_by_name(query)

        if not matches:
            st.error(f"No companies found matching **'{query}'**. Try a ticker symbol instead (e.g. MA for Mastercard).")
            st.stop()

        if len(matches) == 1:
            # Only one result — use it automatically
            m            = matches[0]
            ticker       = m["ticker"]
            cik          = m["cik"]
            company_name = m["title"]
        else:
            # Multiple results — show a dropdown so the user can pick
            options = {f"{m['title']}  ({m['ticker']})": m for m in matches}
            choice  = st.selectbox(
                f"Found {len(matches)} companies matching '{query}' — select one:",
                list(options.keys()),
            )
            if st.button("Confirm selection", type="primary"):
                m            = options[choice]
                ticker       = m["ticker"]
                cik          = m["cik"]
                company_name = m["title"]
            else:
                st.stop()   # wait for the user to confirm before continuing

    if not cik and ticker:
        # Ticker path: cik might still be None if get_company_cik failed
        pass

    if not cik:
        st.error(f"Could not find **{query}** on SEC EDGAR. Check the spelling or try the ticker directly.")
        st.stop()

    # ── DATA + ANALYSIS ───────────────────────────────────────────────────────

    with st.spinner("Downloading 5 years of financial data from EDGAR..."):
        df = build_financials_dataframe(cik)

    ratios = calculate_ratios(df)
    flags  = [flag_ratio(n, v) for n, v in ratios.items()]
    strong = flags.count("Strong")
    total  = len(flags)
    verdict = "STRONG" if strong >= 5 else "MODERATE" if strong >= 3 else "WEAK"

    # ── RESULTS ───────────────────────────────────────────────────────────────

    st.markdown(f"""
    <div style="margin-top:8px;">
        <h2 style="color:#1a237e; font-size:1.5rem; font-weight:800; margin-bottom:4px;">
            {company_name} &nbsp;<span style="color:#888; font-weight:400; font-size:1rem;">({ticker})</span>
        </h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-heading">Overall Verdict</div>', unsafe_allow_html=True)
    st.markdown(render_verdict_banner(verdict, strong, total), unsafe_allow_html=True)

    st.markdown('<div class="section-heading">Ratio Analysis</div>', unsafe_allow_html=True)
    show_ratio_cards(ratios)

    st.markdown('<div class="section-heading">5-Year Revenue Trend</div>', unsafe_allow_html=True)
    show_revenue_chart(df)

    st.markdown('<div class="section-heading">5-Year Financial Summary (USD billions)</div>', unsafe_allow_html=True)
    display_df = df.copy()
    usd_cols = ["revenue","net_income","operating_income","long_term_debt","current_assets","current_liabilities","equity"]
    display_df[usd_cols] = (display_df[usd_cols] / 1_000_000_000).round(2)
    display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
    st.dataframe(display_df, use_container_width=True, height=215)

    st.markdown('<div class="section-heading">Analyst\'s Notes</div>', unsafe_allow_html=True)
    with st.container(border=True):
        try:
            st.write_stream(stream_llama_commentary(company_name, ticker, ratios, df))
        except Exception as e:
            if "api_key" in str(e).lower() or "auth" in str(e).lower():
                st.error("GROQ_API_KEY missing or invalid — check your .env file.")
            else:
                st.error(f"Groq error: {e}")

    st.markdown(
        '<div class="app-footer">Data: SEC EDGAR (public API) &nbsp;·&nbsp; '
        'AI: Llama 3.1 via Groq &nbsp;·&nbsp; Not financial advice.</div>',
        unsafe_allow_html=True,
    )
