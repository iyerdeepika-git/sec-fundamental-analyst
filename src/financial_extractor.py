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
    # Revenue: companies use many different XBRL tags for the same concept.
    # Tech/consumer companies use ASC 606 names; banks use interest income names;
    # older filers still use legacy names. We try the most common ones in order.
    "revenue": (
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueGoodsNet",
            "SalesRevenueServicesNet",
            "RevenuesNetOfInterestExpense",
            "InterestAndNoninterestIncome",
            "TotalRevenues",
        ],
        "USD"
    ),
    "net_income": (
        [
            "NetIncomeLoss",
            "ProfitLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ],
        "USD"
    ),
    "operating_income": (
        [
            "OperatingIncomeLoss",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ],
        "USD"
    ),
    "long_term_debt": (
        ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable"],
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
    "equity": (
        [
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "StockholdersEquity",
            "StockholdersEquityAttributableToParent",
            "PartnersCapital",
        ],
        "USD"
    ),
}


def get_annual_values(facts_data, gaap_fields, unit="USD"):
    """
    Extract annual (10-K only) values for one financial metric.
    Tries each field name in gaap_fields until it finds one with data.

    Returns a dictionary like: {"2024-09-30": 35926000000, "2023-09-30": ...}

    Improvements over v1:
    - Accepts 10-K/A (amended annual reports) — these contain corrected numbers
    - Filters stub periods (short filings when a company shifts its fiscal year-end)
    - When the same fiscal year-end appears in multiple filings, keeps the most
      recently filed value (the most accurate, up-to-date version)
    """
    from datetime import date as _date

    for field in gaap_fields:
        try:
            entries = facts_data["facts"]["us-gaap"][field]["units"][unit]
        except KeyError:
            # This field name doesn't exist for this company — try the next one
            continue

        # best[end_date] = the single best entry for that fiscal year-end.
        # Think of it like a leaderboard: for any given year-end date,
        # only the most recently FILED version earns a slot.
        best = {}

        for entry in entries:
            # Accept both 10-K (original annual) and 10-K/A (amended annual).
            # Previously we only accepted "10-K" — this is what caused missing data.
            if entry.get("form") not in ("10-K", "10-K/A"):
                continue
            if "end" not in entry:
                continue

            # Stub-period filter: if a "start" date is present, the filing must
            # cover at least 300 days to count as a full fiscal year.
            # This removes transition filings like a 3-month stub year.
            if "start" in entry:
                try:
                    start_dt = _date.fromisoformat(entry["start"])
                    end_dt   = _date.fromisoformat(entry["end"])
                    if (end_dt - start_dt).days < 300:
                        continue
                except ValueError:
                    pass  # If dates can't be parsed, keep the entry anyway

            end_key = entry["end"]               # e.g. "2024-09-30"
            filed   = entry.get("filed", "")     # e.g. "2024-11-14"

            # For the same fiscal year-end, keep whichever entry was filed most recently.
            # String comparison works here because dates are in YYYY-MM-DD format —
            # alphabetical order is the same as chronological order for that format.
            if end_key not in best or filed > best[end_key].get("filed", ""):
                best[end_key] = entry

        result = {end: e["val"] for end, e in best.items()}
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
    # Drop years where the two most critical income items are missing —
    # this filters out stub periods and years before a company switched XBRL tags
    df = df.dropna(subset=["revenue", "net_income"])
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
