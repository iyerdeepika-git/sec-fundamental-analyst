# SEC Fundamental Analyst

> An AI-powered financial research assistant that pulls real SEC 10-K filings and performs deep fundamental and ratio analysis on publicly listed US companies — built with Python, Streamlit, and Groq.

---

## What it does

Most financial dashboards show you data. This one reasons about it. SEC Fundamental Analyst connects directly to the **SEC EDGAR API** to fetch real annual filings (no scrapers, no third-party aggregators), extracts the key financial metrics, computes a full suite of fundamental ratios, and then hands everything to a **Groq-powered LLM** to generate an analyst-style narrative — surfacing signals that raw numbers alone won't tell you.

Enter a ticker. Get a research report.

---

## Key Features

- **Real SEC 10-K data** — pulls directly from the SEC EDGAR API (free, no API key required), so you're always working from source-of-truth filings, not estimated or delayed data
- **Full fundamental analysis** — revenue, net income, EPS, total debt, free cash flow, operating margin, and year-over-year trends
- **Ratio analysis** — P/E ratio, debt-to-equity, current ratio, return on equity, and YoY revenue growth, pulled live via `yfinance`
- **AI-assisted insights** — Groq LLM generates a plain-English analyst summary: what the numbers mean, what's healthy, what's worth watching
- **Interactive visualisations** — Plotly charts for trend analysis across filing years
- **Health scoring** — companies are flagged as **Strong**, **Moderate**, or **Weak** based on configurable thresholds across key metrics
- **Clean Streamlit UI** — no dashboards, no noise; just a focused research interface

---

## Tech Stack

| Layer | Tool |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| LLM / AI | [Groq](https://groq.com/) (Llama 3 via Groq API — free tier available) |
| Market data | [yfinance](https://github.com/ranaroussi/yfinance) |
| Filing data | [SEC EDGAR API](https://data.sec.gov/) |
| Data processing | pandas |
| Visualisation | Plotly |
| Config | python-dotenv |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A free Groq API key — get one at [console.groq.com](https://console.groq.com/) (no credit card required)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/iyerdeepika-git/sec-fundamental-analyst.git
cd sec-fundamental-analyst

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your environment
cp .env.example .env
# Open .env and add your Groq API key:
# GROQ_API_KEY=your_api_key_here

# 4. Launch the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

> **Note:** The SEC EDGAR API is free and requires no authentication. Only the Groq API key is needed for AI-generated insights.

---

## Demo
To try it yourself:
1. Run the app locally 
2. Enter a US stock ticker (e.g. `AAPL`, `MSFT`, `V`, `NVDA`)
3. The app fetches the latest 10-K filing and generates a full analysis

---

## Project Structure

```
sec-fundamental-analyst/
├── app.py              # Streamlit entry point
├── src/                # Core analysis logic
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── LEARNINGS.md        # Dev notes and decisions
```

---

## About the Author

Built by **Deepika Iyer** — Financial Data Analyst working at the intersection of finance, data, and AI.

[![LinkedIn](https://img.shields.io/badge/Connect%20on%20LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/deepika-kumar-iyer)
