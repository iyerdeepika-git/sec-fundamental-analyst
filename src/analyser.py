# src/analyser.py
# Job: calculate financial ratios from raw data and flag the company as
# Strong, Moderate, or Weak on each metric — like a quantitative screen.

import math
import pandas as pd

# ── THRESHOLDS ──────────────────────────────────────────────────────────────
# These are the cut-off values that decide each flag.
# Think of them as the "rules of thumb" an analyst uses when screening stocks.
# You can change any of these numbers to match your own investment criteria.
#
# For most ratios: higher is better (Strong > Moderate > Weak).
# Exception: debt_to_equity — lower is better (less debt = stronger balance sheet).

THRESHOLDS = {
    "operating_margin":  {"strong": 0.30, "moderate": 0.15},
    "net_profit_margin": {"strong": 0.20, "moderate": 0.10},
    "revenue_growth":    {"strong": 0.10, "moderate": 0.05},
    "debt_to_equity":    {"strong": 0.50, "moderate": 1.50},
    "current_ratio":     {"strong": 2.00, "moderate": 1.00},
    "return_on_equity":  {"strong": 0.20, "moderate": 0.10},
}


def _safe_div(numerator, denominator):
    """Divide two numbers. Returns NaN if either is missing or denominator is zero."""
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return float("nan")
    return numerator / denominator


def calculate_ratios(df):
    """
    Calculate all six financial ratios from the raw DataFrame.

    df.iloc[0] means "give me row 0" — the most recent year (since we sorted descending).
    df.iloc[1] means "give me row 1" — the previous year, needed for growth calculations.
    Think of iloc as pointing to a row by its position number, like Excel row 2 and row 3.
    """
    latest = df.iloc[0]                              # most recent fiscal year
    prev   = df.iloc[1] if len(df) >= 2 else None   # one year earlier, if available

    ratios = {
        # How much operating profit for every $1 of revenue?
        "operating_margin":  _safe_div(latest["operating_income"], latest["revenue"]),

        # How much net profit for every $1 of revenue?
        "net_profit_margin": _safe_div(latest["net_income"],       latest["revenue"]),

        # How fast is revenue growing year over year?
        # Formula: (this year - last year) / last year
        "revenue_growth": (
            _safe_div(latest["revenue"] - prev["revenue"], prev["revenue"])
            if prev is not None else float("nan")
        ),

        # How much debt relative to shareholder equity?
        "debt_to_equity":    _safe_div(latest["long_term_debt"],        latest["equity"]),

        # Can the company cover its short-term bills with short-term assets?
        "current_ratio":     _safe_div(latest["current_assets"], latest["current_liabilities"]),

        # How much net income is generated per $1 of shareholder equity?
        "return_on_equity":  _safe_div(latest["net_income"],            latest["equity"]),
    }

    return ratios


def flag_ratio(name, value):
    """
    Score a single ratio as Strong, Moderate, Weak, or N/A.

    For all ratios except debt_to_equity: bigger = better.
    For debt_to_equity: smaller = better (less debt is healthier).
    Returns "N/A" if the value is missing (NaN or None).
    """
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
    except (TypeError, ValueError):
        return "N/A"

    t = THRESHOLDS[name]

    if name == "debt_to_equity":
        # Inverted logic — lower debt ratio is stronger
        if value < t["strong"]:      return "Strong"
        elif value < t["moderate"]:  return "Moderate"
        else:                        return "Weak"
    else:
        if value >= t["strong"]:     return "Strong"
        elif value >= t["moderate"]: return "Moderate"
        else:                        return "Weak"


def format_value(name, value):
    """Format a ratio value for display — percentages as %, ratios as plain numbers."""
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
    except (TypeError, ValueError):
        return "N/A"

    if name == "debt_to_equity" or name == "current_ratio":
        return f"{value:.2f}x"
    else:
        return f"{value * 100:.1f}%"


def print_analysis(company_name, fiscal_year, ratios):
    """Print a clean analyst-style summary report to the terminal."""

    flag_display = {"Strong": "[ STRONG   ]", "Moderate": "[ MODERATE ]", "Weak": "[ WEAK     ]"}

    print(f"\n{'='*58}")
    print(f"  {company_name} — Fundamental Analysis ({fiscal_year})")
    print(f"{'='*58}")
    print(f"  {'Ratio':<25} {'Value':>8}   {'Flag'}")
    print(f"  {'-'*50}")

    for name, value in ratios.items():
        flag   = flag_ratio(name, value)
        label  = name.replace("_", " ").title()
        formatted = format_value(name, value)
        print(f"  {label:<25} {formatted:>8}   {flag_display[flag]}")

    # Count how many Strong flags
    flags = [flag_ratio(n, v) for n, v in ratios.items()]
    strong_count = flags.count("Strong")
    total        = len(flags)

    print(f"  {'-'*50}")

    # Overall verdict based on majority of flags
    if strong_count >= 5:
        verdict = "STRONG"
    elif strong_count >= 3:
        verdict = "MODERATE"
    else:
        verdict = "WEAK"

    print(f"  Overall verdict: {verdict}  ({strong_count}/{total} metrics rated Strong)")
    print(f"{'='*58}\n")


def calculate_confidence_score(ratios, df):
    """
    Rate data completeness from 1 (severe gaps) to 5 (fully complete).

    Two factors are weighted together:
      - 60%  ratio completeness: how many of the 6 ratios have real values
      - 40%  year completeness:  how many of the 5 years have ≥5 of 7 columns filled

    Returns an integer 1–5.
    """
    def _valid(v):
        """True if v is a real number (not None or NaN)."""
        try:
            return v is not None and not math.isnan(float(v))
        except (TypeError, ValueError):
            return False

    ratio_completeness = sum(1 for v in ratios.values() if _valid(v)) / max(len(ratios), 1)

    # A year is considered "complete" if at least 5 of its 7 data columns are filled
    complete_years = sum(1 for _, row in df.iterrows() if row.notna().sum() >= 5)
    year_completeness = complete_years / max(len(df), 1)

    raw_score = (ratio_completeness * 0.6 + year_completeness * 0.4) * 5
    return max(1, min(5, round(raw_score)))


def find_data_gaps(ratios, df):
    """
    Return a list of plain-English descriptions of every missing data point.
    Used in the confidence badge UI and passed as context to the LLM prompt.
    """
    gaps = []

    # Ratio-level gaps: any metric the analyser couldn't compute
    for name, value in ratios.items():
        if flag_ratio(name, value) == "N/A":
            label = name.replace("_", " ").title()
            gaps.append(f"{label} unavailable from EDGAR")

    # Year-level gaps: individual columns missing for specific fiscal years
    for year in df.index:
        missing_cols = [c for c in df.columns if pd.isna(df.loc[year, c])]
        if missing_cols:
            cols_str = ", ".join(c.replace("_", " ").title() for c in missing_cols)
            gaps.append(f"FY{str(year)[:4]}: {cols_str} missing")

    return gaps


# ── QUICK TEST ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from edgar_fetcher import get_company_cik
    from financial_extractor import build_financials_dataframe

    cik = get_company_cik("V")
    df  = build_financials_dataframe(cik)

    # Calculate all ratios using the most recent two years
    ratios = calculate_ratios(df)

    # The fiscal year end date of the most recent row
    fiscal_year = df.index[0]

    print_analysis("VISA INC.", fiscal_year, ratios)
