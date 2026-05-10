# src/peer_fetcher.py
# Job: fetch financial ratios for a company via Yahoo Finance (yfinance).
# Used for the peer comparison section — faster than EDGAR for multiple companies.

import yfinance as yf


def fetch_peer_ratios(ticker_symbol):
    """
    Fetch the 6 core financial ratios for a ticker using Yahoo Finance.

    Returns a dict like:
        {
            "ticker":       "MA",
            "company_name": "Mastercard Incorporated",
            "ratios": {
                "operating_margin":  0.582,
                "net_profit_margin": 0.461,
                ...
            }
        }
    Returns None if the ticker is invalid or Yahoo Finance has no data.

    Note on yfinance vs EDGAR:
    - EDGAR gives raw numbers that we calculate ratios from ourselves.
    - yfinance gives pre-calculated ratios directly from Yahoo's data feed.
    - Minor differences in values can occur due to methodology (e.g. TTM vs FY).
    """
    try:
        # yf.Ticker("MA") creates a Ticker object — like opening a company's folder
        # in Yahoo Finance. Nothing is downloaded yet; this just sets up the connection.
        ticker = yf.Ticker(ticker_symbol.upper().strip())

        # .info is a Python dictionary (~100 pre-calculated fields) that Yahoo serves
        # for this company. Think of it as the summary page on Yahoo Finance,
        # but in machine-readable format. This is where the actual data download happens.
        info = ticker.info

        # If Yahoo returns an empty dict or the ticker doesn't exist, bail out early.
        # We check for "symbol" because every valid ticker response includes it.
        if not info or "symbol" not in info:
            return None

        def _get(key):
            """
            Safely read a value from the info dict.
            If the key is missing or the value is None, return float("nan") —
            Python's way of representing a blank/unknown number (like #N/A in Excel).
            """
            val = info.get(key)
            return float("nan") if val is None else float(val)

        # IMPORTANT: yfinance reports debtToEquity as a PERCENTAGE (e.g. 150.0)
        # but our EDGAR-based ratios use decimals (e.g. 1.5 = 150%).
        # We divide by 100 here so both sources use the same scale.
        raw_dte = info.get("debtToEquity")
        debt_to_equity = float("nan") if raw_dte is None else float(raw_dte) / 100

        return {
            "ticker":       ticker_symbol.upper().strip(),
            "company_name": info.get("longName") or ticker_symbol.upper().strip(),
            "ratios": {
                "operating_margin":  _get("operatingMargins"),
                "net_profit_margin": _get("profitMargins"),
                "revenue_growth":    _get("revenueGrowth"),
                "debt_to_equity":    debt_to_equity,
                "current_ratio":     _get("currentRatio"),
                "return_on_equity":  _get("returnOnEquity"),
            },
        }

    except Exception:
        # If anything goes wrong (network error, unexpected data format),
        # return None so the app can show a warning rather than crash.
        return None
