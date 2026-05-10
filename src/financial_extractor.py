# src/financial_extractor.py
# Job: extract key annual financial metrics from SEC EDGAR's company facts API
# and return them as a clean pandas DataFrame (think: a spreadsheet in Python)

import requests   # makes web requests to the SEC API
import pandas as pd  # gives us DataFrames — spreadsheets in Python

HEADERS = {"User-Agent": "sec-fundamental-analyst iyerdeepikakumar@gmail.com"}
EDGAR_BASE_URL = "https://data.sec.gov"

# Each metric maps to a LIST of possible GAAP field names, ordered by preference.
# Why a list? Different companies file the same concept under different names.
# We try each name in order and use the first one that actually has data.
# Think of it like trying several synonyms until the filing cabinet responds.
METRICS = {
    # Visa adopted ASC 606 in 2019 and switched field names — try the newer one first
    "revenue": (
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        "USD"
    ),
    "net_income": (
        ["NetIncomeLoss"],
        "USD"
    ),
    "operating_income": (
        ["OperatingIncomeLoss"],
        "USD"
    ),
    "long_term_debt": (
        ["LongTermDebtNoncurrent", "LongTermDebt"],
        "USD"
    ),
    "current_assets": (
        ["AssetsCurrent"],
        "USD"
    ),
    "current_liabilities": (
        ["LiabilitiesCurrent"],
        "USD"
    ),
    # Visa reports equity including non-controlling interests — try that first
    "equity": (
        ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
         "StockholdersEquity",
         "StockholdersEquityAttributableToParent"],
        "USD"
    ),
    # NOTE: EarningsPerShareDiluted and WeightedAverageNumberOfDilutedSharesOutstanding
    # are not available in Visa's EDGAR XBRL data. EPS can be sourced separately
    # (e.g. Yahoo Finance) and added in a future iteration.
}


def get_annual_values(facts_data, gaap_fields, unit="USD"):
    """
    Extract annual (10-K only) values for one financial metric.
    Tries each field name in gaap_fields until it finds one with data.

    Returns a dictionary like: {"2024-09-30": 35926000000, "2023-09-30": ...}
    """
    for field in gaap_fields:
        try:
            entries = facts_data["facts"]["us-gaap"][field]["units"][unit]
        except KeyError:
            # This field name doesn't exist for this company — try the next one
            continue

        result = {}
        for entry in entries:
            # Only keep annual 10-K entries, not quarterly 10-Q
            if entry.get("form") == "10-K" and "end" in entry:
                result[entry["end"]] = entry["val"]

        if result:
            # Found real data — no need to try the remaining field names
            return result

    # None of the field names worked
    return {}


def build_financials_dataframe(cik):
    """
    Fetch all financial facts for a company and return a clean DataFrame.
    Rows = fiscal year end dates. Columns = financial metrics.
    """
    url = f"{EDGAR_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
    print(f"Fetching financial data from EDGAR for CIK {cik}...")

    response = requests.get(url, headers=HEADERS)
    facts = response.json()

    all_data = {}
    for metric_name, (gaap_fields, unit) in METRICS.items():
        all_data[metric_name] = get_annual_values(facts, gaap_fields, unit)
        found = "✓" if all_data[metric_name] else "✗ NOT FOUND"
        print(f"  {metric_name}: {found}")

    # Convert our dictionary of dictionaries into a DataFrame (spreadsheet)
    df = pd.DataFrame(all_data)
    df.index.name = "fiscal_year_end"
    df = df.sort_index(ascending=False)
    df = df.head(5)

    return df


# --- QUICK TEST ---
if __name__ == "__main__":
    from edgar_fetcher import get_company_cik

    cik = get_company_cik("V")
    print("---")

    df = build_financials_dataframe(cik)

    print("\n=== VISA INC. — Annual Financial Data ===")
    display = df.copy()
    usd_cols = ["revenue", "net_income", "operating_income",
                "long_term_debt", "current_assets", "current_liabilities", "equity"]
    display[usd_cols] = (display[usd_cols] / 1_000_000).round(1)

    print(display.to_string())
    print("\n(All values in USD millions)")
