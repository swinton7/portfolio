"""Config, database and Ollama helpers shared by ingest, api and evaluate."""
import psycopg
import requests
import yaml

CFG = yaml.safe_load(open("/config.yaml"))

# nomic-embed-text is trained with task prefixes; documents and queries get different ones.
PREFIX = {"document": "search_document: ", "query": "search_query: "}


def connect():
    return psycopg.connect(CFG["database_url"], autocommit=True)


def check_ollama():
    try:
        tags = requests.get(f"{CFG['ollama_url']}/api/tags", timeout=5).json()
    except requests.ConnectionError:
        raise SystemExit(f"Ollama is not reachable at {CFG['ollama_url']}. Install it from https://ollama.com and start it.")
    have = {m["name"] for m in tags["models"]} | {m["name"].removesuffix(":latest") for m in tags["models"]}
    missing = [m for m in (CFG["embed_model"], CFG["chat_model"]) if m not in have]
    if missing:
        raise SystemExit(f"Missing Ollama models: run `ollama pull {' && ollama pull '.join(missing)}` on the host.")


def embed(texts, kind):
    resp = requests.post(
        f"{CFG['ollama_url']}/api/embed",
        json={"model": CFG["embed_model"], "input": [PREFIX[kind] + t for t in texts]},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def to_vector(values):
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
