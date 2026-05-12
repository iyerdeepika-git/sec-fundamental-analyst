# SEC Fundamental Analyst — Build Learnings

Everything you learned building this project, written for future-you to reference.

---

## 1. Python Fundamentals

### NaN — the "blank cell" of Python numbers
```python
float("nan")   # Python's version of Excel's #N/A
```
- NaN is never equal to itself: `v != v` is **True only for NaN** (IEEE 754 rule)
- Use `math.isnan(float(v))` or `pd.isna(v)` to check for it
- Always return `float("nan")` — not `None` — when a number is missing, so math still works downstream

### Safe division
```python
def _safe_div(numerator, denominator):
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return float("nan")
    return numerator / denominator
```
Finance analogy: like a Bloomberg function that returns `#N/A` instead of crashing when data is missing.

### try / except — catching errors gracefully
```python
try:
    result = risky_operation()
except (TypeError, ValueError):
    result = float("nan")   # carry on with a blank instead of crashing
except Exception:
    return None             # catch everything — used in API wrappers
```
Rule of thumb: wrap **external calls** (APIs, network requests) in broad `except Exception`. Wrap **internal math** only in the specific errors you expect.

### Generators and `yield`
```python
def stream_text():
    for chunk in api_response:
        yield chunk          # produces one piece at a time, never loads it all at once
```
Finance analogy: like a Bloomberg data feed — data arrives tick by tick, not all at once. `st.write_stream` consumes a generator to show text as it arrives.

**Gotcha:** `st.write_stream` can return `None` if the stream produces nothing. Always coerce: `result = st.write_stream(...) or ""`.

### List comprehensions — compact filtering
```python
confirmed = [p for p in [peer1, peer2] if p]   # keep only non-None peers
valid     = [(i, v) for i, v in enumerate(values) if v is not None and v == v]
```
`v == v` is False only for NaN — a compact NaN filter.

### f-strings
```python
f"EV/EBITDA: {value:.1f}x"    # .1f = 1 decimal place
f"${value / 1e9:.1f}B"        # divide by 1 billion, show 1 decimal
```

---

## 2. pandas

### DataFrames are spreadsheets
- Rows = observations (fiscal years), Columns = metrics
- `df.iloc[0]` = row 0 by position (most recent year after sorting descending)
- `df.iloc[1]` = row 1 = prior year (needed for YoY growth)
- `df.empty` = True when the DataFrame has 0 rows

### Selecting by position vs label
```python
df.iloc[0]          # by position — use when order matters (most recent)
df.loc["2024-09-30"] # by label — use when you know the exact index value
```

### Dropping rows with missing data
```python
df.dropna(subset=["revenue", "net_income"])
```
Removes any row where **either** revenue **or** net income is blank. This is why some companies return empty DataFrames — their GAAP field names don't match what we search for.

### Sorting
```python
df.sort_index(ascending=False)   # most recent year first
```

---

## 3. Streamlit

### The golden rule: every interaction causes a full rerun
Every button click, dropdown change, or text input re-runs the entire `app.py` from top to bottom. This means:
- Variables defined earlier in the script are **recalculated** on every click
- You cannot store results in regular Python variables — they reset every run
- You must use `st.session_state` to persist anything across interactions

### session_state — the app's memory
```python
# Initialise (only runs the first time the key doesn't exist)
if "peer_results" not in st.session_state:
    st.session_state.peer_results = None

# Read
result = st.session_state.peer_results
result = st.session_state.get("peer_results")   # safer — returns None if missing

# Write
st.session_state.peer_results = companies
```
Finance analogy: like a Bloomberg panel — values persist even as you switch between screens.

### st.button — True only on the click rerun
```python
if st.button("Compare Peers →"):
    # This block runs ONCE — on the rerun triggered by the click
    # On every other rerun, st.button returns False
    st.session_state.peer_results = companies   # must save to session_state!
```
Common mistake: trying to use a variable set inside a button block on a later rerun — it won't exist. Always persist to `session_state`.

### st.stop() — abort the script
```python
if df.empty:
    st.error("No data found.")
    st.stop()   # everything below this line is skipped
```
Useful as a guard clause — like an early `return` but for the whole page.

### st.rerun() — force a fresh render
```python
st.session_state.confirmed = selected_company
st.rerun()   # immediately re-run the script so the UI reflects the new state
```
Use sparingly — mostly needed after setting session_state that the current render pass already passed.

### st.write_stream — for live AI output
```python
result = st.write_stream(generator_function())
# result is the collected text (can be None — always coerce with `or ""`)
```

### Caching expensive operations in session_state
```python
if st.session_state.financials_cik != cik:
    df = build_financials_dataframe(cik)        # only fetch from EDGAR when company changes
    st.session_state.financials_df  = df
    st.session_state.financials_cik = cik
else:
    df = st.session_state.financials_df         # reuse cached result
```
Without this, every button click re-downloads the data — wasting network calls and hitting rate limits.

### unsafe_allow_html — render raw HTML
```python
st.markdown("<div style='color:red'>text</div>", unsafe_allow_html=True)
```
This is how the metric cards, verdict banners, and comparison table are built — gives full CSS control inside Streamlit.

---

## 4. SEC EDGAR API

### How the API works
Two key endpoints:
1. **Company index:** `https://www.sec.gov/files/company_tickers.json`
   - Maps ticker → CIK (company ID) + company name
   - Downloaded as one big JSON, ~1MB
2. **Company facts:** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
   - All XBRL financial data ever filed for one company
   - Structured as `facts → us-gaap → FieldName → units → USD → [entries]`

### CIK — the EDGAR company ID
Every company has a unique 10-digit CIK (Central Index Key). Always zero-pad:
```python
cik = str(company["cik_str"]).zfill(10)   # "895421" → "0000895421"
```

### XBRL field names vary by company
Different companies use different GAAP tag names for the same concept:
- Apple uses `RevenueFromContractWithCustomerExcludingAssessedTax`
- JPMorgan uses `RevenueFromContractWithCustomerExcludingAssessedTax` or `Revenues`
- Older filings use `SalesRevenueNet`

Solution: try a prioritised list of field names, use the first one that has data.

### 10-K vs 10-K/A
- `10-K` = original annual report
- `10-K/A` = amended (corrected) annual report — contains more accurate numbers
- Always accept both, and for the same fiscal year-end, keep the **most recently filed** version

### Stub period filter
Companies occasionally change their fiscal year-end, filing a short "transition" period (e.g. 3 months). These look like annual filings but aren't.
```python
if (end_date - start_date).days < 300:
    continue   # skip — not a full fiscal year
```

### Rate limiting
EDGAR throttles repeated requests. Fix: cache the DataFrame in `session_state` so EDGAR is only called **once per company per session**, not on every button click.

### Minimising API calls
`get_company_info` (ticker lookup) and `search_companies_by_name` (name search) both need the same `company_tickers.json`. Download it once, pass it to both:
```python
data = _load_company_tickers()
cik, title = get_company_info(query, _data=data)
if not cik:
    matches = search_companies_by_name(query, _data=data)
```

---

## 5. yfinance

### What it does
Fetches live market data (price, P/E, market cap) from Yahoo Finance. Much faster than EDGAR for quick lookups, but **unreliable on cloud hosting** (rate limits, SSL issues).

### The debtToEquity scale mismatch — critical gotcha
yfinance reports `debtToEquity` as a **percentage** (e.g. `150.0`), but EDGAR-based calculations use **decimals** (e.g. `1.5`). Always divide by 100 when mixing sources:
```python
raw_dte = info.get("debtToEquity")
debt_to_equity = float("nan") if raw_dte is None else float(raw_dte) / 100
```

### Prefer EDGAR for fundamentals
Now that the peer search widget returns a CIK, peer ratio data is fetched from EDGAR (same methodology as the primary company). yfinance is only used for **valuation multiples** (P/E, EV/EBITDA, etc.) because those require live market prices that EDGAR doesn't have.

---

## 6. AI / LLM Integration (Groq)

### System prompt vs user prompt
```python
messages=[
    {"role": "system", "content": "You are an analyst. Be specific."},
    {"role": "user",   "content": f"Analyse {company_name}: revenue = {revenue}..."},
]
```
- **System prompt:** sets the persona, rules, and output format. Never changes.
- **User prompt:** the specific data for this run. Changes every time.

### Forcing structured output
Include exact headings in your prompt:
> "Your response MUST contain exactly three sections with these headers: **Bull Case**, **Bear Case**, **Overall Verdict**"

Without this, the LLM invents its own structure — which breaks any rendering logic that depends on it.

### Streaming
```python
stream = client.chat.completions.create(..., stream=True)
for chunk in stream:
    text = chunk.choices[0].delta.content
    if text:
        yield text
```
Streaming yields tokens as they're generated. `st.write_stream` consumes this generator and shows each word as it arrives — much better UX than waiting for the full response.

---

## 7. Debugging Lessons

### Silent crashes in Streamlit
Some exceptions are swallowed without showing a red error box. Symptoms:
- A button does nothing (no table, no warning, no error)
- The page looks the same before and after clicking

Causes we hit:
- `st.markdown(None)` → TypeError (from caching `st.write_stream`'s `None` return)
- Uncaught exception in a button handler → handler aborts silently

Fix: wrap risky code in `try/except` and always show a visible error message.

### Checking Streamlit Cloud logs
Click **"Manage app"** (bottom right corner of your deployed app) → **Logs**. All `print()` statements appear here. Add `print(f"peer_df shape: {peer_df.shape}")` before a bug to see exactly what the data looks like in production.

### The EDGAR empty DataFrame bug
Search "space" → EDGAR finds the company → `build_financials_dataframe` returns 0 rows → `df.iloc[0]` raises `IndexError`. Fix: check `df.empty` immediately after building the DataFrame, before any further processing.

### st.write_stream returns None
Streamlit's documentation says `st.write_stream` returns the collected text **or None**. Always coerce:
```python
result = st.write_stream(my_generator())
st.session_state.cache = result or ""      # never store None
```
Then guard display:
```python
st.markdown(st.session_state.cache or "")  # never pass None to st.markdown
```

---

## 8. Git Workflow

### Conventional Commits format
```
feat:     new user-facing feature
fix:      bug fix
refactor: code change with no behaviour change
docs:     documentation only
```

### Committing in PowerShell (Windows)
Use single-quoted here-strings for multi-line messages:
```powershell
git commit -m @'
feat: add peer comparison table

Description of what changed and why.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
'@
```

### Deploy to Streamlit Cloud
1. Commit changes locally
2. `git push origin main`
3. Streamlit Cloud auto-detects the push and redeploys (~30–60 seconds)
4. Watch the "Deploying" spinner in the top-right corner of your app

### Secrets on Streamlit Cloud
Never commit API keys. Add them in **Streamlit Cloud → App settings → Secrets**:
```toml
GROQ_API_KEY = "your_key_here"
```
Read them in code with fallback for local development:
```python
api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
```

---

## 9. Architecture Decisions

### EDGAR vs yfinance — when to use each

| Purpose | Source | Why |
|---|---|---|
| Historical ratio data (primary company) | EDGAR | Audited 10-K filings, full 5-year history |
| Historical ratio data (peer companies) | EDGAR | Consistent methodology with primary |
| Valuation multiples (P/E, EV/EBITDA) | yfinance | Live market prices — EDGAR doesn't have these |
| Company search / CIK lookup | EDGAR | Authoritative source for all SEC registrants |

### Why session_state for everything
Streamlit's rerun model means any data not in `session_state` is lost on the next user interaction. The pattern used throughout this app:
1. Check if the cached value is still valid (same company? same ticker?)
2. If not: fetch, compute, store in `session_state`
3. If yes: read from `session_state` directly

This prevents redundant network calls and keeps the UI fast.
