# src/edgar_fetcher.py
# Job: connect to SEC EDGAR and fetch 10-K filing data for a given company

import requests  # lets Python make web requests (like a browser, but in code)

# The SEC requires all API users to identify themselves in every request.
# Think of this like signing a visitor log before entering a government building.
# Without this, the SEC will block our requests.
HEADERS = {
    "User-Agent": "sec-fundamental-analyst iyerdeepikakumar@gmail.com"
}

# The base URL for SEC EDGAR's data API — we'll attach different endings to this
EDGAR_BASE_URL = "https://data.sec.gov"


def get_company_cik(ticker):
    """
    Look up a company's CIK number using their stock ticker symbol.

    What is a CIK? It stands for Central Index Key — the SEC's unique ID
    for every publicly listed company. Like a passport number, but for companies.
    Visa's ticker is 'V'. We need their CIK to fetch their filings.
    """
    # This URL points to a JSON file the SEC publishes listing every
    # public company alongside their ticker and CIK number
    url = "https://www.sec.gov/files/company_tickers.json"

    # Send the request to the SEC — like asking a librarian for the index card
    response = requests.get(url, headers=HEADERS)

    # The SEC sends back data in JSON format.
    # JSON is like a structured spreadsheet — organised into labelled boxes.
    # .json() converts it from raw text into a Python dictionary we can search.
    data = response.json()

    # Loop through every company in the list to find the one we want.
    # 'data.values()' gives us each company's info one at a time.
    for company in data.values():
        if company["ticker"].upper() == ticker.upper():
            # CIK numbers must always be exactly 10 digits.
            # .zfill(10) pads short numbers with leading zeros — e.g. 12345 -> 0000012345
            cik = str(company["cik_str"]).zfill(10)
            print(f"Found {company['title']} — CIK: {cik}")
            return cik

    # If we get here, the ticker wasn't found
    print(f"Could not find a company with ticker: {ticker}")
    return None


def get_company_info(ticker):
    """
    Like get_company_cik() but also returns the company's full registered name.
    Returns a (cik, title) tuple, e.g. ("0001403161", "VISA INC.").
    Returns (None, None) if the ticker isn't found.
    """
    url      = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=HEADERS)
    data     = response.json()
    for company in data.values():
        if company["ticker"].upper() == ticker.upper():
            cik = str(company["cik_str"]).zfill(10)
            return cik, company["title"]
    return None, None


def get_recent_10k(cik):
    """
    Fetch the most recent 10-K filing for a company using their CIK number.

    Returns the accession number — a unique ID for that specific filing.
    Think of it like a document reference number on a legal contract.
    """
    # Build the URL for this company's full filing history
    url = f"{EDGAR_BASE_URL}/submissions/CIK{cik}.json"

    # Ask EDGAR for the filing history
    response = requests.get(url, headers=HEADERS)
    data = response.json()

    # The filings are stored inside data["filings"]["recent"]
    # This is a dictionary where each key is a column — like a spreadsheet.
    # "form" is one column (10-K, 10-Q, 8-K...), "filingDate" is another.
    filings = data["filings"]["recent"]

    # Loop through every filing and find 10-K entries
    # zip() lets us walk through two lists side by side at the same time —
    # like reading two columns of a spreadsheet row by row
    for form, date, accession in zip(
        filings["form"],
        filings["filingDate"],
        filings["accessionNumber"]
    ):
        if form == "10-K":
            # We found the most recent 10-K — return it immediately
            print(f"Most recent 10-K filed on: {date}")
            print(f"Accession number: {accession}")
            return accession

    print("No 10-K filing found.")
    return None


def search_companies_by_name(query, max_results=8):
    """
    Search the SEC company list by company name (not ticker).
    Returns a list of dicts: [{"ticker": "MA", "cik": "...", "title": "Mastercard Inc"}, ...]

    Why this works: the same JSON file we use for ticker lookup also has every
    company's full name in the "title" field. We just search that field instead.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=HEADERS)
    data = response.json()

    query_lower = query.lower().strip()
    matches = []
    for company in data.values():
        if query_lower in company["title"].lower():
            matches.append({
                "ticker": company["ticker"],
                "cik":    str(company["cik_str"]).zfill(10),
                "title":  company["title"],
            })

    # Put closest matches first: names that START with the query beat ones that contain it
    matches.sort(key=lambda x: (
        0 if x["title"].lower().startswith(query_lower) else 1,
        x["title"]
    ))
    return matches[:max_results]


# --- QUICK TEST ---
# This block only runs when you execute THIS file directly (not when imported).
# Think of it as a "test drive" button for this specific file.
if __name__ == "__main__":
    cik = get_company_cik("V")
    print(f"Visa's CIK number is: {cik}")
    print("---")
    accession = get_recent_10k(cik)
    print(f"We will extract data from filing: {accession}")
