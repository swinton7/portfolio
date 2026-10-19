"""Simulate an application writing to Postgres: new payments, status changes and the odd delete."""
import random
import time

import psycopg2

conn = psycopg2.connect(host="postgres", dbname="shop", user="postgres", password="postgres")
conn.autocommit = True
cur = conn.cursor()

while True:
    action = random.choices(["insert", "update", "delete"], weights=[6, 3, 1])[0]
    if action == "insert":
        cur.execute(
            "INSERT INTO payments (merchant_id, amount) VALUES (%s, %s) RETURNING id",
            (f"m_{random.randint(1, 10):04d}", round(random.uniform(100, 5000), 2)),
        )
    elif action == "update":
        cur.execute(
            """UPDATE payments SET status = %s, updated_at = now()
               WHERE id = (SELECT id FROM payments WHERE status = 'pending' ORDER BY random() LIMIT 1)
               RETURNING id""",
            (random.choices(["paid", "failed"], weights=[8, 2])[0],),
        )
    else:
        cur.execute(
            "DELETE FROM payments WHERE id = (SELECT id FROM payments WHERE status = 'failed' LIMIT 1) RETURNING id"
        )
    row = cur.fetchone()
    if row:
        print(f"{action:<6} payment {row[0]}", flush=True)
    time.sleep(0.5)
