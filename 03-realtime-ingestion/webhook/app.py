"""Receive Debezium change events over HTTP and maintain realtime aggregates in Redis."""
import json
import os
import time

import redis
from fastapi import FastAPI, Request

app = FastAPI()
r = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), decode_responses=True)


@app.post("/events")
async def events(request: Request):
    event = await request.json()
    op, payment_id = event["__op"], event["id"]

    # Idempotency: Debezium is at-least-once, so skip an event we have already applied.
    event_key = f"seen:{payment_id}:{op}:{event['__source_ts_ms']}"
    if not r.set(event_key, 1, nx=True, ex=3600):
        return {"duplicate": True}

    previous = r.hgetall(f"payment:{payment_id}")
    pipe = r.pipeline()
    if previous:
        pipe.hincrby("stats:status", previous["status"], -1)
        if previous["status"] == "paid":
            pipe.zincrby("leaderboard:merchant_paid", -float(previous["amount"]), previous["merchant_id"])

    if event.get("__deleted") == "true" or op == "d":
        pipe.delete(f"payment:{payment_id}")
    else:
        pipe.hset(f"payment:{payment_id}", mapping={k: event[k] for k in ("merchant_id", "amount", "status")})
        pipe.hincrby("stats:status", event["status"], 1)
        if event["status"] == "paid":
            pipe.zincrby("leaderboard:merchant_paid", float(event["amount"]), event["merchant_id"])

    pipe.hincrby("stats:ops", op, 1)
    pipe.set("stats:last_lag_ms", int(time.time() * 1000) - int(event["__source_ts_ms"]))
    pipe.xadd("stream:payment_events", {"payload": json.dumps(event)}, maxlen=1000, approximate=True)
    pipe.execute()
    return {"applied": True}


@app.get("/stats")
def stats():
    return {
        "events_by_op": r.hgetall("stats:ops"),
        "payments_by_status": {k: int(v) for k, v in r.hgetall("stats:status").items() if int(v)},
        "top_merchants_by_paid_amount": {
            m: round(score, 2) for m, score in r.zrevrange("leaderboard:merchant_paid", 0, 4, withscores=True)
        },
        "last_event_lag_ms": r.get("stats:last_lag_ms"),
        "event_log_length": r.xlen("stream:payment_events"),
    }


@app.get("/health")
def health():
    return {"redis": r.ping()}
