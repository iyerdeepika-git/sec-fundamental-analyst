# SEC Fundamental Analyst

A Python tool that fetches real 10-K filings from the SEC EDGAR database and performs fundamental financial analysis on publicly listed US companies.

## What it does

- Connects to the **SEC EDGAR API** (free, no API key required) to pull real 10-K annual filings
- Extracts key financial metrics: revenue, net income, EPS, total debt, free cash flow, operating margin
- Calculates fundamental ratios: P/E, debt-to-equity, current ratio, return on equity, YoY revenue growth
- Flags companies as **Strong**, **Moderate**, or **Weak** based on configurable thresholds
- Outputs a clean summary report as CSV and HTML

## Example output

Analysis of **Visa Inc. (V)** — based on the latest 10-K filing.

## Tech stack

- Python 3.10+
- `requests` — for fetching data from the SEC EDGAR API
- `pandas` — for storing and manipulating financial data
- `matplotlib` — for charts and visualisations

## How to run

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/sec-fundamental-analyst.git

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the analyser
python src/main.py
```

## Project structure

```
sec-fundamental-analyst/
├── data/           Raw data from SEC EDGAR
├── outputs/        Generated reports (CSV, HTML)
├── src/            Python source code
├── tests/          Unit tests
└── requirements.txt
```

## Author

Built by Deepika Iyer — Financial Data Analyst
