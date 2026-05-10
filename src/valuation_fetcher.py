# src/valuation_fetcher.py
# Job: fetch live market/valuation metrics for a company via yfinance.
# These metrics need live market prices so they cannot come from EDGAR.

import yfinance as yf

# The 5 valuation metrics we want.
# Each entry: key → (yfinance field name, display label)
VALUATION_METRICS = {
    "market_cap":    ("marketCap",           "Market Cap"),
    "trailing_pe":   ("trailingPE",          "P/E Trailing"),
    "forward_pe":    ("forwardPE",           "P/E Forward"),
    "ev_ebitda":     ("enterpriseToEbitda",  "EV / EBITDA"),
    "price_to_book": ("priceToBook",         "Price / Book"),
}

# Short "Typical:" hint shown directly on each card beneath the number.
# None means this metric has no universal "typical" range worth showing.
VALUATION_TYPICAL = {
    "market_cap":    None,
    "trailing_pe":   "Typical: 15–25x",
    "forward_pe":    "Compare vs. trailing",
    "ev_ebitda":     "Typical: 10–15x",
    "price_to_book": "Typical: 1–3x",
}

# Full explanation + range context for the expandable footnote.
VALUATION_CONTEXT = {
    "market_cap": {
        "label": "Market Capitalisation",
        "what":  "Total market value of all shares outstanding — a measure of company size, not quality.",
        "range": "Mega-cap > $200B  ·  Large-cap $10–200B  ·  Mid-cap $2–10B  ·  Small-cap < $2B",
    },
    "trailing_pe": {
        "label": "P/E Ratio (Trailing)",
        "what":  "The price investors pay for every $1 of last year's earnings. A P/E of 20x means you're paying $20 for $1 of annual profit.",
        "range": "Cheap < 15x  ·  Fair 15–25x  ·  Pricey > 30x  (varies heavily by sector — tech runs higher, banks lower)",
    },
    "forward_pe": {
        "label": "P/E Ratio (Forward)",
        "what":  "Same as trailing P/E but uses analysts' estimates of next year's earnings instead of last year's. A forward P/E below trailing P/E implies the market expects earnings to grow.",
        "range": "Compare against the trailing P/E and sector peers rather than a fixed number",
    },
    "ev_ebitda": {
        "label": "EV / EBITDA",
        "what":  "Enterprise Value (market cap + net debt) divided by EBITDA (operating earnings before interest, tax, depreciation, amortisation). Better than P/E for comparing companies with very different debt levels.",
        "range": "Cheap < 10x  ·  Fair 10–15x  ·  Pricey > 20x  (tech/growth companies often trade at 30–50x)",
    },
    "price_to_book": {
        "label": "Price / Book",
        "what":  "Share price divided by book value per share (net assets per share). A ratio above 1x means the market values the company above its accounting net worth — usually because of brand, IP, or high returns on equity.",
        "range": "Below 1x = trading at discount to assets  ·  1–3x = typical  ·  Above 5x = high premium (normal for asset-light companies like Visa, Mastercard)",
    },
}


def fetch_valuation_metrics(ticker_symbol):
    """
    Fetch the 5 valuation metrics for a ticker from Yahoo Finance.

    Returns a dict like: {"market_cap": 500e9, "trailing_pe": 23.4, ...}
    Returns None if the ticker is invalid or Yahoo Finance has no data.
    """
    try:
        info = yf.Ticker(ticker_symbol.upper().strip()).info

        # If Yahoo can't find the ticker, it returns a near-empty dict
        if not info or "symbol" not in info:
            return None

        result = {}
        for key, (yf_field, _label) in VALUATION_METRICS.items():
            val = info.get(yf_field)
            # Store as float("nan") if missing — consistent with our NaN convention
            result[key] = float("nan") if val is None else float(val)

        return result

    except Exception:
        return None


def format_valuation_value(key, value):
    """
    Format a valuation metric value for display.

    market_cap  → "$1.2T", "$450.3B", "$8.1M"
    all others  → "23.4x"
    missing     → "N/A"
    """
    # NaN check: NaN is never equal to itself (v != v is True only for NaN)
    if value is None or value != value:
        return "N/A"

    if key == "market_cap":
        if value >= 1e12:  return f"${value / 1e12:.1f}T"
        if value >= 1e9:   return f"${value / 1e9:.1f}B"
        return f"${value / 1e6:.1f}M"

    # All other metrics are multiples — show as "23.4x"
    # Negative values happen when a company is losing money (negative P/E is valid)
    return f"{value:.1f}x"
