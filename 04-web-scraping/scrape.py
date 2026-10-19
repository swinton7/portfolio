"""Crawl the merchant directory politely and land raw HTML + parsed JSONL in MinIO."""
import json
import os
import time
from datetime import date
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import boto3
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = os.environ["BASE_URL"]
BUCKET = "scrape"
USER_AGENT = "portfolio-scraper/1.0"
RUN_DATE = date.today().isoformat()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
)
if BUCKET not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
    s3.create_bucket(Bucket=BUCKET)

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
session.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])))

robots = RobotFileParser()
robots.parse(session.get(urljoin(BASE_URL, "/robots.txt"), timeout=10).text.splitlines())
delay = robots.crawl_delay(USER_AGENT) or 0

url, page_no, records = urljoin(BASE_URL, "/merchants"), 1, []
while url:
    if not robots.can_fetch(USER_AGENT, url):
        print(f"robots.txt disallows {url}, stopping")
        break
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    s3.put_object(
        Bucket=BUCKET,
        Key=f"raw/merchants/dt={RUN_DATE}/page-{page_no:03d}.html",
        Body=resp.content,
        ContentType="text/html",
        Metadata={"source-url": url},
    )

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("tr.merchant")
    records += [
        {
            "merchant_id": row.select_one(".id").text,
            "name": row.select_one(".name").text,
            "category": row.select_one(".category").text,
            "city": row.select_one(".city").text,
            "rating": float(row.select_one(".rating").text),
            "scraped_at": RUN_DATE,
            "source_url": url,
        }
        for row in rows
    ]
    print(f"page {page_no}: {len(rows)} merchants")

    next_link = soup.select_one("a.next")
    url = urljoin(BASE_URL, next_link["href"]) if next_link else None
    page_no += 1
    time.sleep(delay)

s3.put_object(
    Bucket=BUCKET,
    Key=f"parsed/merchants/dt={RUN_DATE}/merchants.jsonl",
    Body="\n".join(json.dumps(r) for r in records).encode(),
    ContentType="application/x-ndjson",
)

objects = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"raw/merchants/dt={RUN_DATE}/")["KeyCount"]
print(f"landed {objects} raw pages and {len(records)} parsed merchants in s3://{BUCKET} (dt={RUN_DATE})")
