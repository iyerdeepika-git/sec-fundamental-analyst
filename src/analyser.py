# src/analyser.py
# Job: calculate financial ratios from raw data and flag the company as
# Strong, Moderate, or Weak on each metric — like a quantitative screen.

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


def calculate_ratios(df):
    """
    Calculate all six financial ratios from the raw DataFrame.

    df.iloc[0] means "give me row 0" — the most recent year (since we sorted descending).
    df.iloc[1] means "give me row 1" — the previous year, needed for growth calculations.
    Think of iloc as pointing to a row by its position number, like Excel row 2 and row 3.
    """
    latest = df.iloc[0]   # most recent fiscal year
    prev   = df.iloc[1]   # one year earlier

    ratios = {
        # How much operating profit for every $1 of revenue?
        "operating_margin":  latest["operating_income"] / latest["revenue"],

        # How much net profit for every $1 of revenue?
        "net_profit_margin": latest["net_income"] / latest["revenue"],

        # How fast is revenue growing year over year?
        # Formula: (this year - last year) / last year
        "revenue_growth":    (latest["revenue"] - prev["revenue"]) / prev["revenue"],

        # How much debt relative to shareholder equity?
        # Like asking: for every $1 of equity, how much has been borrowed?
        "debt_to_equity":    latest["long_term_debt"] / latest["equity"],

        # Can the company cover its short-term bills with short-term assets?
        # A ratio above 1.0 means yes. Below 1.0 means potential liquidity risk.
        "current_ratio":     latest["current_assets"] / latest["current_liabilities"],

        # How much net income is generated per $1 of shareholder equity?
        # The higher this is, the harder equity is working for investors.
        "return_on_equity":  latest["net_income"] / latest["equity"],
    }

    return ratios


def flag_ratio(name, value):
    """
    Score a single ratio as Strong, Moderate, or Weak.

    For all ratios except debt_to_equity: bigger = better.
    For debt_to_equity: smaller = better (less debt is healthier).
    """
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
