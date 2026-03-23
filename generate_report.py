import os
import json
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────
GSC_PROPERTY      = os.environ["GSC_PROPERTY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
REPORT_TO_EMAIL   = os.environ["REPORT_TO_EMAIL"]
SERVICE_ACCOUNT_INFO = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])

TRACKED_POSTS = [
    {
        "label": "Fabric Sofa vs Leather Sofa",
        "url": "/blogs/home/fabric-sofa-vs-leather-sofa-an-honest-breakdown-for-singapore-homes",
    },
    {
        "label": "Perfect Sofa Size for HDB",
        "url": "/blogs/home/how-to-pick-the-perfect-sofa-size-for-your-singapore-hdb-flat",
    },
    {
        "label": "Understanding Mattress Types",
        "url": "/blogs/home/understanding-mattress-types-pocket-spring-vs-memory-foam-vs-latex",
    },
    {
        "label": "BTO Furniture Checklist",
        "url": "/blogs/home/the-ultimate-bto-furniture-checklist-what-to-buy-first-and-what-can-wait",
    },
]

# ── GSC helpers ───────────────────────────────────────────────────────────────
def build_gsc_service():
    scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
    creds  = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    return build("searchconsole", "v1", credentials=creds)

def date_range(days_back=28):
    end   = datetime.date.today() - datetime.timedelta(days=3)   # GSC lag
    start = end - datetime.timedelta(days=days_back - 1)
    return str(start), str(end)

def fetch_site_summary(svc, start, end):
    resp = svc.searchanalytics().query(
        siteUrl=GSC_PROPERTY,
        body={"startDate": start, "endDate": end,
              "dimensions": ["date"],
              "rowLimit": 28}
    ).execute()
    rows = resp.get("rows", [])
    clicks_by_day = {r["keys"][0]: int(r["clicks"]) for r in rows}
    total_clicks  = sum(r["clicks"] for r in rows)
    total_imps    = sum(r["impressions"] for r in rows)
    avg_ctr       = (total_clicks / total_imps * 100) if total_imps else 0
    avg_pos       = sum(r["position"] for r in rows) / len(rows) if rows else 0
    return {
        "total_clicks": int(total_clicks),
        "total_impressions": int(total_imps),
        "avg_ctr": round(avg_ctr, 2),
        "avg_position": round(avg_pos, 1),
        "clicks_by_day": clicks_by_day,
    }

def fetch_top_pages(svc, start, end, n=10):
    resp = svc.searchanalytics().query(
        siteUrl=GSC_PROPERTY,
        body={"startDate": start, "endDate": end,
              "dimensions": ["page"],
              "rowLimit": n}
    ).execute()
    return resp.get("rows", [])

def fetch_post_metrics(svc, start, end, post_url):
    full_url = f"https://www.novafurnishing.com{post_url}"
    try:
        resp = svc.searchanalytics().query(
            siteUrl=GSC_PROPERTY,
            body={"startDate": start, "endDate": end,
                  "dimensions": ["page"],
                  "dimensionFilterGroups": [{"filters": [
                      {"dimension": "page", "operator": "equals", "expression": full_url}
                  ]}],
                  "rowLimit": 1}
        ).execute()
        rows = resp.get("rows", [])
        if rows:
            r = rows[0]
            return {"clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
                    "ctr": round(r["ctr"]*100, 2), "position": round(r["position"], 1)}
    except Exception:
        pass
    return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}

# ── SVG chart ─────────────────────────────────────────────────────────────────
def svg_bar_chart(clicks_by_day, width=540, height=120):
    if not clicks_by_day:
        return ""
    dates  = sorted(clicks_by_day.keys())[-14:]          # last 14 days
    values = [clicks_by_day.get(d, 0) for d in dates]
    max_v  = max(values) if max(values) > 0 else 1
    bar_w  = width // len(dates)
    bars   = ""
    for i, (d, v) in enumerate(zip(dates, values)):
        bh = max(2, int(v / max_v * (height - 20)))
        x  = i * bar_w + 2
        y  = height - bh - 10
        color = "#2563eb" if i == len(dates)-1 else "#93c5fd"
        bars += f'<rect x="{x}" y="{y}" width="{bar_w-4}" height="{bh}" rx="3" fill="{color}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'style="display:block;margin:0 auto">{bars}</svg>')

def progress_bar(value, max_value, color="#2563eb", width=200):
    pct = min(100, int(value / max_value * 100)) if max_value else 0
    return (f'<div style="background:#e5e7eb;border-radius:4px;height:10px;width:{width}px;display:inline-block;vertical-align:middle">'
            f'<div style="background:{color};border-radius:4px;height:10px;width:{pct}%"></div></div>'
            f'<span style="font-size:12px;color:#6b7280;margin-left:6px">{pct}%</span>')

def trend_arrow(val, threshold=0):
    if val > threshold:  return '<span style="color:#16a34a;font-size:16px">&#9650;</span>'
    if val < threshold:  return '<span style="color:#dc2626;font-size:16px">&#9660;</span>'
    return '<span style="color:#6b7280;font-size:14px">&#9654;</span>'

# ── Email builder ─────────────────────────────────────────────────────────────
def build_html(summary, post_data, top_pages, chart_svg, start, end):
    today = datetime.date.today().strftime("%d %b %Y")
    period = f"{datetime.datetime.strptime(start,'%Y-%m-%d').strftime('%d %b')} – {datetime.datetime.strptime(end,'%Y-%m-%d').strftime('%d %b %Y')}"

    post_rows = ""
    for p in post_data:
        m = p["metrics"]
        color = "#16a34a" if m["clicks"] >= 10 else ("#f59e0b" if m["clicks"] >= 3 else "#dc2626")
        badge_text = "Good" if m["clicks"] >= 10 else ("Growing" if m["clicks"] >= 3 else "Low")
        post_rows += f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151">{p['label']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:13px;font-weight:600;color:#111827">{m['clicks']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:13px;color:#6b7280">{m['impressions']:,}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:13px;color:#6b7280">{m['ctr']}%</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:13px;color:#6b7280">#{m['position']}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #f3f4f6;text-align:center">
            <span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600">{badge_text}</span>
          </td>
        </tr>"""

    top_page_rows = ""
    for i, r in enumerate(top_pages[:8], 1):
        url = r["keys"][0].replace("https://www.novafurnishing.com","")
        short = (url[:55] + "…") if len(url) > 55 else url
        top_page_rows += f"""
        <tr>
          <td style="padding:8px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;color:#6b7280;text-align:center">{i}</td>
          <td style="padding:8px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;color:#374151">{short}</td>
          <td style="padding:8px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:12px;font-weight:600;color:#2563eb">{int(r['clicks'])}</td>
          <td style="padding:8px 8px;border-bottom:1px solid #f3f4f6;text-align:center;font-size:12px;color:#6b7280">{int(r['impressions']):,}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;margin:32px auto">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);border-radius:12px 12px 0 0;padding:28px 32px">
    <p style="margin:0;color:#bfdbfe;font-size:12px;letter-spacing:1px;text-transform:uppercase">Nova Furnishing · SEO Weekly Report</p>
    <h1 style="margin:8px 0 4px;color:#fff;font-size:22px;font-weight:700">Search Performance Report</h1>
    <p style="margin:0;color:#93c5fd;font-size:13px">Period: {period} &nbsp;|&nbsp; Generated: {today}</p>
  </td></tr>

  <!-- KPI Cards -->
  <tr><td style="background:#fff;padding:24px 32px 16px">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td width="25%" style="text-align:center;padding:0 6px">
          <div style="background:#eff6ff;border-radius:10px;padding:16px 8px">
            <div style="font-size:26px;font-weight:800;color:#1d4ed8">{summary['total_clicks']:,}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px">Total Clicks</div>
          </div>
        </td>
        <td width="25%" style="text-align:center;padding:0 6px">
          <div style="background:#f0fdf4;border-radius:10px;padding:16px 8px">
            <div style="font-size:26px;font-weight:800;color:#16a34a">{summary['total_impressions']:,}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px">Impressions</div>
          </div>
        </td>
        <td width="25%" style="text-align:center;padding:0 6px">
          <div style="background:#fefce8;border-radius:10px;padding:16px 8px">
            <div style="font-size:26px;font-weight:800;color:#ca8a04">{summary['avg_ctr']}%</div>
            <div style="font-size:11px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px">Avg CTR</div>
          </div>
        </td>
        <td width="25%" style="text-align:center;padding:0 6px">
          <div style="background:#fdf4ff;border-radius:10px;padding:16px 8px">
            <div style="font-size:26px;font-weight:800;color:#9333ea">#{summary['avg_position']}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:4px;text-transform:uppercase;letter-spacing:.5px">Avg Position</div>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Chart -->
  <tr><td style="background:#fff;padding:8px 32px 24px">
    <p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:.5px">Daily Clicks — Last 14 Days</p>
    {chart_svg}
    <p style="text-align:center;font-size:11px;color:#9ca3af;margin:6px 0 0">Blue = most recent day</p>
  </td></tr>

  <!-- Tracked Posts -->
  <tr><td style="background:#fff;padding:4px 32px 24px">
    <p style="margin:0 0 12px;font-size:13px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:.5px">SEO-Optimised Blog Posts (FAQ Schema)</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <thead>
        <tr style="background:#f9fafb">
          <th style="padding:8px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">POST</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">CLICKS</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">IMPS</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">CTR</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">POS</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">STATUS</th>
        </tr>
      </thead>
      <tbody>{post_rows}</tbody>
    </table>
  </td></tr>

  <!-- Top Pages -->
  <tr><td style="background:#fff;padding:4px 32px 24px;border-radius:0 0 12px 12px">
    <p style="margin:0 0 12px;font-size:13px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:.5px">Top 8 Pages by Clicks</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <thead>
        <tr style="background:#f9fafb">
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">#</th>
          <th style="padding:8px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">PAGE</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">CLICKS</th>
          <th style="padding:8px;text-align:center;font-size:11px;color:#9ca3af;font-weight:600;border-bottom:2px solid #e5e7eb">IMPS</th>
        </tr>
      </thead>
      <tbody>{top_page_rows}</tbody>
    </table>
  </td></tr>

  <!-- Next Actions -->
  <tr><td style="padding:16px 0">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="background:#1e293b;border-radius:12px;padding:24px 32px">
        <p style="margin:0 0 16px;color:#94a3b8;font-size:12px;letter-spacing:1px;text-transform:uppercase">Weekly Action Checklist</p>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:6px 0">
              <span style="color:#4ade80;font-size:14px">&#10003;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">FAQ Schema added to 4 priority posts</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#4ade80;font-size:14px">&#10003;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">Schema validated — 0 errors at validator.schema.org</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#4ade80;font-size:14px">&#10003;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">URL Indexing requested via Google Search Console</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#fbbf24;font-size:14px">&#9654;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">Add internal links (min. 3 per post) per internal links map</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#fbbf24;font-size:14px">&#9654;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">Update nav &amp; footer to link /blogs/home</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#fbbf24;font-size:14px">&#9654;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">Fix duplicate posts — 301 redirects for 2 confirmed dupes</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#fbbf24;font-size:14px">&#9654;</span>
              <span style="color:#e2e8f0;font-size:13px;margin-left:8px">Create Ashton Wong author page + update 106 post authors</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0">
              <span style="color:#fb923c;font-size:14px">&#9675;</span>
              <span style="color:#94a3b8;font-size:13px;margin-left:8px">Add "From Our Blog" section to homepage</span>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0;color:#475569;font-size:11px">&#10003; Done &nbsp; &#9654; In Progress &nbsp; &#9675; Pending</p>
      </td></tr>
    </table>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:0 0 32px;text-align:center">
    <p style="margin:0;color:#9ca3af;font-size:11px">
      Nova Furnishing SEO Automation &nbsp;|&nbsp; Auto-generated every Monday 9am SGT<br>
      Data from Google Search Console &nbsp;·&nbsp; <a href="https://www.novafurnishing.com" style="color:#6b7280">novafurnishing.com</a>
    </p>
  </td></tr>

</table>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    svc = build_gsc_service()
    start, end = date_range(28)

    print(f"Fetching GSC data: {start} to {end}")
    summary    = fetch_site_summary(svc, start, end)
    top_pages  = fetch_top_pages(svc, start, end, n=10)
    chart_svg  = svg_bar_chart(summary["clicks_by_day"])

    post_data = []
    for p in TRACKED_POSTS:
        metrics = fetch_post_metrics(svc, start, end, p["url"])
        post_data.append({"label": p["label"], "url": p["url"], "metrics": metrics})
        print(f"  {p['label']}: {metrics}")

    print(f"Site totals: {summary['total_clicks']} clicks, {summary['total_impressions']} impressions")

    html_body = build_html(summary, post_data, top_pages, chart_svg, start, end)

    # Send email via Gmail SMTP
    msg = MIMEMultipart("alternative")
    today_str = datetime.date.today().strftime("%d %b %Y")
    msg["Subject"] = f"[Nova Furnishing] Weekly SEO Report — {today_str}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = REPORT_TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, REPORT_TO_EMAIL, msg.as_string())

    print("Email sent successfully.")

if __name__ == "__main__":
    main()
