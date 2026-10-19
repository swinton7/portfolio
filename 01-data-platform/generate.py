"""Generate mock payments + a provider settlement file and land them in MinIO (raw zone)."""
import os

import boto3
import duckdb

BUCKET = "lake"
ENDPOINT = os.environ["S3_ENDPOINT"]
KEY, SECRET = os.environ["S3_ACCESS_KEY"], os.environ["S3_SECRET_KEY"]

s3 = boto3.client("s3", endpoint_url=f"http://{ENDPOINT}", aws_access_key_id=KEY, aws_secret_access_key=SECRET)
if BUCKET not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
    s3.create_bucket(Bucket=BUCKET)

con = duckdb.connect()
con.execute("LOAD httpfs")
con.execute(f"""
    CREATE SECRET minio (TYPE S3, KEY_ID '{KEY}', SECRET '{SECRET}', ENDPOINT '{ENDPOINT}',
                         USE_SSL false, URL_STYLE 'path', REGION 'us-east-1')
""")
con.execute("SELECT setseed(0.42)")

con.execute("""
    CREATE TABLE payments AS
    SELECT
        'pay_' || lpad(i::VARCHAR, 6, '0')                                   AS payment_id,
        'm_' || lpad((1 + floor(random() * 50))::INT::VARCHAR, 4, '0')       AS merchant_id,
        (10000 + floor(random() * 490000))::BIGINT                           AS amount,
        'PHP'                                                                AS currency,
        (['card', 'gcash', 'qrph', 'maya'])[1 + floor(random() * 4)::INT]   AS method,
        CASE WHEN random() < 0.90 THEN 'paid'
             WHEN random() < 0.6  THEN 'failed' ELSE 'refunded' END          AS status,
        TIMESTAMP '2026-10-01' + INTERVAL (floor(random() * 14 * 86400)) SECOND AS created_at
    FROM range(1, 20001) t(i)
""")

con.execute("""
    CREATE TABLE settlements AS
    SELECT
        payment_id                                                             AS reference,
        CASE WHEN random() < 0.01 THEN amount - 100 ELSE amount END / 100.0   AS settled_amount,
        round(amount * 0.025) / 100.0                                          AS fee,
        (created_at + INTERVAL 1 DAY)::DATE                                    AS settlement_date
    FROM payments
    WHERE status = 'paid' AND random() > 0.02
    UNION ALL
    SELECT 'pay_9' || lpad(i::VARCHAR, 5, '0'), 250.00, 6.25, DATE '2026-10-10'
    FROM range(1, 16) t(i)
""")

con.execute(f"COPY payments TO 's3://{BUCKET}/raw/payments' (FORMAT parquet, PARTITION_BY (status), OVERWRITE_OR_IGNORE)")
con.execute(f"COPY settlements TO 's3://{BUCKET}/raw/settlements/provider_settlements.csv' (HEADER)")

for table in ("payments", "settlements"):
    print(f"landed {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>6} rows -> raw/{table}")
