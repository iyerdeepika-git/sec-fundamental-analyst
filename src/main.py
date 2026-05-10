# src/main.py
# The entry point for the entire project.
# Run this one file and it does everything:
#   1. Looks up the company on SEC EDGAR
#   2. Downloads their financial data
#   3. Calculates ratios and scores
#   4. Saves a CSV and an HTML report

from edgar_fetcher      import get_company_cik
from financial_extractor import build_financials_dataframe
from analyser           import calculate_ratios, print_analysis
from reporter           import save_csv, save_html_report

# ── CONFIGURATION ─────────────────────────────────────────────────────────
# Change these two values to analyse a different company
TICKER       = "V"
COMPANY_NAME = "Visa Inc."
# ──────────────────────────────────────────────────────────────────────────


def run():
    print(f"\nStarting analysis for {COMPANY_NAME} ({TICKER})...")
    print("-" * 50)

    # Step 1: Get the SEC identifier for this company
    cik = get_company_cik(TICKER)
    if not cik:
        print("Could not find company. Check the ticker symbol.")
        return

    # Step 2: Download 5 years of financial data from EDGAR
    df = build_financials_dataframe(cik)

    # Step 3: Calculate ratios and print the analysis to the terminal
    ratios      = calculate_ratios(df)
    fiscal_year = df.index[0]
    print_analysis(COMPANY_NAME, fiscal_year, ratios)

    # Step 4: Save outputs
    save_csv(df, COMPANY_NAME)
    save_html_report(df, ratios, COMPANY_NAME, TICKER, fiscal_year)

    print("\nDone. Open outputs/v_report.html in your browser to see the full report.")


# This pattern means: only run() when this file is executed directly.
# If another script imports main.py, run() won't fire automatically.
if __name__ == "__main__":
    run()
