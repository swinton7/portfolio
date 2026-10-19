set -e

echo "== 1. generate raw data into MinIO"
python generate.py

echo "== 2. dbt build (bronze -> silver -> gold, with tests)"
cd dbt
dbt build --target-path /tmp/target --log-path /tmp/logs

echo "== 3. reconciliation result (read back from s3://lake/gold)"
python - <<'EOF'
import os, duckdb
con = duckdb.connect()
con.execute("LOAD httpfs")
con.execute(f"""CREATE SECRET (TYPE S3, KEY_ID '{os.environ["S3_ACCESS_KEY"]}', SECRET '{os.environ["S3_SECRET_KEY"]}',
    ENDPOINT '{os.environ["S3_ENDPOINT"]}', USE_SSL false, URL_STYLE 'path', REGION 'us-east-1')""")
con.sql("""SELECT match_status, count(*) AS payments, sum(expected_amount) AS expected, sum(settled_amount) AS settled
           FROM 's3://lake/gold/reconciliation.parquet' GROUP BY 1 ORDER BY 2 DESC""").show()
EOF
