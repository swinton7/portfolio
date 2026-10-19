"""Log into the merchant portal, download a settlement report and capture evidence (screenshots + trace)."""
import csv
import os
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ["BASE_URL"]
OUT = Path("/output")
REPORT_DATE = (date.today() - timedelta(days=1)).isoformat()

OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 800})
    context.tracing.start(screenshots=True, snapshots=True)
    page = context.new_page()

    print("1. wrong password is rejected")
    page.goto(f"{BASE_URL}/login")
    page.fill("#username", "demo")
    page.fill("#password", "wrong")
    page.click("#submit")
    expect(page.locator("#error")).to_be_visible()
    page.screenshot(path=OUT / "01-login-error.png")

    print("2. log in")
    page.fill("#username", "demo")
    page.fill("#password", "demo")
    page.click("#submit")
    expect(page).to_have_url(f"{BASE_URL}/reports")
    page.screenshot(path=OUT / "02-reports.png")

    print(f"3. download settlement report for {REPORT_DATE}")
    page.fill("#report-date", REPORT_DATE)
    with page.expect_download() as download_info:
        page.click("#download")
    download = download_info.value
    target = OUT / download.suggested_filename
    download.save_as(target)

    context.tracing.stop(path=OUT / "trace.zip")
    browser.close()

with target.open() as f:
    rows = list(csv.DictReader(f))
total = sum(float(r["net_amount"]) for r in rows)
print(f"4. saved {target.name}: {len(rows)} merchants, net {total:,.2f}")
print(f"   evidence in ./output: {', '.join(sorted(x.name for x in OUT.iterdir()))}")
