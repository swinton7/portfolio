"""A tiny fake merchant portal used as the target for scraping and browser automation."""
import csv
import io
import random
from datetime import date

from fastapi import Cookie, FastAPI, Form, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse

app = FastAPI()

USERNAME, PASSWORD, SESSION = "demo", "demo", "demo-session"
PAGE_SIZE, TOTAL_MERCHANTS = 20, 95
CATEGORIES = ["food", "retail", "travel", "services", "digital"]
CITIES = ["Manila", "Cebu", "Davao", "Jakarta", "Singapore"]

_rng = random.Random(42)
MERCHANTS = [
    {
        "merchant_id": f"m_{i:04d}",
        "name": f"Merchant {i:04d}",
        "category": _rng.choice(CATEGORIES),
        "city": _rng.choice(CITIES),
        "rating": round(_rng.uniform(3.0, 5.0), 1),
    }
    for i in range(1, TOTAL_MERCHANTS + 1)
]


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html><head><title>{title}</title>
<style>body{{font-family:sans-serif;margin:2rem}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:4px 8px}}</style></head>
<body><h1>{title}</h1>{body}</body></html>"""
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return page(
        "Mock Merchant Portal",
        '<ul><li><a href="/merchants">Merchant directory (public)</a></li>'
        '<li><a href="/login">Login to settlement reports</a></li></ul>',
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /merchants\nDisallow: /reports\nCrawl-delay: 1\n"


@app.get("/merchants", response_class=HTMLResponse)
def merchants(page_no: int = Query(1, alias="page")):
    start = (page_no - 1) * PAGE_SIZE
    rows = MERCHANTS[start : start + PAGE_SIZE]
    trs = "".join(
        f'<tr class="merchant"><td class="id">{m["merchant_id"]}</td><td class="name">{m["name"]}</td>'
        f'<td class="category">{m["category"]}</td><td class="city">{m["city"]}</td>'
        f'<td class="rating">{m["rating"]}</td></tr>'
        for m in rows
    )
    nav = f'<a class="next" href="/merchants?page={page_no + 1}">Next</a>' if start + PAGE_SIZE < TOTAL_MERCHANTS else ""
    return page(
        f"Merchant directory - page {page_no}",
        f"<table><tr><th>ID</th><th>Name</th><th>Category</th><th>City</th><th>Rating</th></tr>{trs}</table><p>{nav}</p>",
    )


@app.get("/login", response_class=HTMLResponse)
def login_form(error: str = ""):
    msg = '<p id="error" style="color:red">Invalid credentials</p>' if error else ""
    return page(
        "Login",
        f"""{msg}<form method="post" action="/login">
<label>Username <input id="username" name="username"></label><br><br>
<label>Password <input id="password" name="password" type="password"></label><br><br>
<button id="submit" type="submit">Sign in</button></form><p>Hint: demo / demo</p>""",
    )


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if (username, password) != (USERNAME, PASSWORD):
        return RedirectResponse("/login?error=1", status_code=303)
    resp = RedirectResponse("/reports", status_code=303)
    resp.set_cookie("session", SESSION)
    return resp


@app.get("/reports", response_class=HTMLResponse)
def reports(session: str | None = Cookie(None)):
    if session != SESSION:
        return RedirectResponse("/login", status_code=303)
    return page(
        "Settlement reports",
        f"""<form method="get" action="/reports/download">
<label>Settlement date <input id="report-date" name="report_date" type="date" value="{date.today()}"></label>
<button id="download" type="submit">Download CSV</button></form>""",
    )


@app.get("/reports/download")
def download(report_date: date, session: str | None = Cookie(None)):
    if session != SESSION:
        return RedirectResponse("/login", status_code=303)
    rng = random.Random(report_date.toordinal())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["settlement_date", "merchant_id", "transaction_count", "gross_amount", "fee", "net_amount"])
    for m in rng.sample(MERCHANTS, 25):
        count = rng.randint(5, 400)
        gross = round(count * rng.uniform(150, 2500), 2)
        fee = round(gross * 0.025, 2)
        writer.writerow([report_date, m["merchant_id"], count, gross, fee, round(gross - fee, 2)])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="settlement_{report_date}.csv"'},
    )


@app.get("/health")
def health():
    return {"ok": True}
