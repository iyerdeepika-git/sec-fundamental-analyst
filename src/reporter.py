# src/reporter.py
# Job: take our financial data and analysis results and save them as
# a CSV file (for Excel) and an HTML report (for sharing / portfolio).

import os
import pandas as pd
from datetime import date


def save_csv(df, company_name, output_dir="outputs"):
    """
    Save the raw financial DataFrame to a CSV file.
    CSV (Comma-Separated Values) is a plain text format that Excel opens natively.
    Think of it as saving a spreadsheet without any formatting.
    """
    # Make sure the outputs folder exists — os.makedirs won't crash if it already does
    os.makedirs(output_dir, exist_ok=True)

    # Build the filename: e.g. "visa_financials.csv"
    # .lower() makes the name lowercase, .replace(" ", "_") swaps spaces for underscores
    filename = f"{company_name.lower().replace(' ', '_')}_financials.csv"
    filepath = os.path.join(output_dir, filename)

    # df.to_csv() writes the DataFrame to disk, exactly like File > Save As in Excel
    df.to_csv(filepath)
    print(f"CSV saved: {filepath}")
    return filepath


def save_html_report(df, ratios, company_name, ticker, fiscal_year, output_dir="outputs"):
    """
    Generate a clean, styled HTML report and save it to the outputs folder.
    HTML is a file format that any web browser can open — like a mini-website.
    """
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{ticker.lower()}_report.html"
    filepath = os.path.join(output_dir, filename)

    # Build the financial data table rows (5 years of data)
    # We'll display values in millions with one decimal place
    usd_cols = ["revenue", "net_income", "operating_income",
                "long_term_debt", "current_assets", "current_liabilities", "equity"]
    display_df = df.copy()
    display_df[usd_cols] = (display_df[usd_cols] / 1_000_000).round(1)

    table_rows = ""
    for idx, row in display_df.iterrows():
        cells = f"<td>{idx}</td>"
        for col in display_df.columns:
            val = row[col]
            cells += f"<td>{val:,.1f}</td>" if pd.notna(val) else "<td>—</td>"
        table_rows += f"<tr>{cells}</tr>\n"

    # Build the ratio rows with colour-coded flags
    flag_colours = {"Strong": "#2e7d32", "Moderate": "#e65100", "Weak": "#c62828"}
    ratio_rows = ""
    from analyser import flag_ratio, format_value, THRESHOLDS
    for name, value in ratios.items():
        flag   = flag_ratio(name, value)
        colour = flag_colours[flag]
        label  = name.replace("_", " ").title()
        formatted = format_value(name, value)
        ratio_rows += f"""
        <tr>
            <td>{label}</td>
            <td>{formatted}</td>
            <td style="color:{colour}; font-weight:bold;">{flag}</td>
        </tr>"""

    # Overall verdict
    flags        = [flag_ratio(n, v) for n, v in ratios.items()]
    strong_count = flags.count("Strong")
    total        = len(flags)
    if strong_count >= 5:   verdict, vcolour = "STRONG",   "#2e7d32"
    elif strong_count >= 3: verdict, vcolour = "MODERATE", "#e65100"
    else:                   verdict, vcolour = "WEAK",     "#c62828"

    # Column headers for the data table
    col_headers = "<th>Fiscal Year End</th>" + "".join(
        f"<th>{c.replace('_', ' ').title()}</th>" for c in display_df.columns
    )

    # The full HTML document — inline CSS keeps it self-contained (no external files needed)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{company_name} — Fundamental Analysis</title>
    <style>
        body        {{ font-family: Arial, sans-serif; max-width: 960px; margin: 40px auto; color: #1a1a1a; }}
        h1          {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 8px; }}
        h2          {{ color: #283593; margin-top: 36px; }}
        table       {{ border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 14px; }}
        th          {{ background: #1a237e; color: white; padding: 10px 12px; text-align: left; }}
        td          {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
        tr:hover    {{ background: #f5f5f5; }}
        .verdict    {{ font-size: 22px; font-weight: bold; margin: 16px 0; color: {vcolour}; }}
        .meta       {{ color: #757575; font-size: 13px; margin-top: -6px; }}
        .footer     {{ margin-top: 48px; font-size: 12px; color: #9e9e9e; border-top: 1px solid #e0e0e0; padding-top: 12px; }}
    </style>
</head>
<body>
    <h1>{company_name} ({ticker.upper()}) — Fundamental Analysis</h1>
    <p class="meta">Most recent fiscal year: {fiscal_year} &nbsp;|&nbsp; Report generated: {date.today()} &nbsp;|&nbsp; Data source: SEC EDGAR</p>

    <h2>Overall Verdict</h2>
    <p class="verdict">{verdict} &nbsp; ({strong_count}/{total} metrics rated Strong)</p>

    <h2>Ratio Analysis</h2>
    <table>
        <tr><th>Metric</th><th>Value</th><th>Flag</th></tr>
        {ratio_rows}
    </table>

    <h2>5-Year Financial Summary (USD millions)</h2>
    <table>
        <tr>{col_headers}</tr>
        {table_rows}
    </table>

    <div class="footer">
        Built with sec-fundamental-analyst &nbsp;|&nbsp; Data from SEC EDGAR (free public API) &nbsp;|&nbsp; Not financial advice.
    </div>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report saved: {filepath}")
    return filepath
