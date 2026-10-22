"""POST /ask: hybrid retrieval over MedlinePlus chunks, then a local LLM names the matching conditions."""
import json
import time

import requests
from fastapi import FastAPI
from pydantic import BaseModel

from common import CFG, connect, embed, to_vector

app = FastAPI(title="Symptom RAG")
conn = connect()

# Vector and keyword candidates are ranked separately, then merged with reciprocal rank fusion.
# The keyword query ORs the symptom words, so a chunk that matches only some of them still counts.
HYBRID_SQL = """
WITH vec AS (
    SELECT id, row_number() OVER (ORDER BY embedding <=> %(embedding)s::vector) AS rnk
    FROM chunks ORDER BY embedding <=> %(embedding)s::vector LIMIT %(candidates)s
), kw AS (
    SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS rnk
    FROM chunks, (SELECT replace(plainto_tsquery('english', %(text)s)::text, ' & ', ' | ')::tsquery AS q) AS k
    WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q) DESC LIMIT %(candidates)s
)
SELECT c.title, c.url, c.content,
       coalesce(1.0 / (%(rrf_k)s + vec.rnk), 0) + coalesce(1.0 / (%(rrf_k)s + kw.rnk), 0) AS score,
       vec.rnk AS vector_rank, kw.rnk AS keyword_rank
FROM vec FULL JOIN kw USING (id) JOIN chunks c USING (id)
ORDER BY score DESC LIMIT %(top_k)s
"""

SYSTEM = """You match a person's symptoms to health conditions described in numbered MedlinePlus excerpts.
Use only the excerpts. List up to 5 conditions, best match first.
For each condition: "name" is the excerpt title exactly as written, "why" is one sentence naming the
symptoms that match, and "sources" are the excerpt numbers you used.
If no excerpt fits the symptoms, return an empty list. Never give treatment or dosing advice.
Reply with JSON only, in this shape:
{"conditions": [{"name": "...", "why": "...", "sources": [1, 2]}]}"""


class Question(BaseModel):
    symptoms: str


def retrieve(text):
    params = {"embedding": to_vector(embed([text], "query")[0]), "text": text, **CFG["retrieval"]}
    cur = conn.execute(HYBRID_SQL, params)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def generate(symptoms, chunks):
    excerpts = "\n\n".join(f"[{n}] {c['content']}" for n, c in enumerate(chunks, 1))
    resp = requests.post(f"{CFG['ollama_url']}/api/chat", timeout=300, json={
        "model": CFG["chat_model"],
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Symptoms: {symptoms}\n\nExcerpts:\n\n{excerpts}"}],
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "num_predict": CFG["generation"]["num_predict"]},
    })
    resp.raise_for_status()
    out = resp.json()
    meta = {"done_reason": out["done_reason"], "tokens": out["eval_count"]}
    # Ollama has no structured output for qwen3.5 yet, so the JSON is asked for in the prompt and cut
    # out of the reply; an answer that does not parse is reported through done_reason, not raised.
    content = out["message"]["content"]
    try:
        return json.loads(content[content.index("{"):content.rindex("}") + 1])["conditions"], meta
    except (ValueError, KeyError):
        return [], {**meta, "unparsed": content}


@app.post("/ask")
def ask(q: Question):
    t0 = time.perf_counter()
    chunks = retrieve(q.symptoms)
    t1 = time.perf_counter()
    conditions, generation = generate(q.symptoms, chunks)
    t2 = time.perf_counter()

    sources = [{"n": n, "title": c["title"], "url": c["url"]} for n, c in enumerate(chunks, 1)]
    for cond in conditions:
        # Chunks start with "Title (also called: ...)" and small models copy all of it into the name.
        cond["name"] = str(cond.get("name", "")).split(" (also called")[0].strip()
        # Keep only citations that point at a real excerpt; evaluate.py checks the rest.
        cond["sources"] = [sources[n - 1] for n in dict.fromkeys(cond.get("sources", []))
                           if isinstance(n, int) and 1 <= n <= len(sources)]
    return {
        "disclaimer": CFG["disclaimer"],
        "attribution": CFG["attribution"],
        "conditions": conditions,
        "retrieved": [{**s, "score": round(float(c["score"]), 4), "vector_rank": c["vector_rank"],
                       "keyword_rank": c["keyword_rank"]} for s, c in zip(sources, chunks)],
        "generation": generation,
        "timings_ms": {"retrieve": round((t1 - t0) * 1000), "generate": round((t2 - t1) * 1000)},
    }


@app.get("/health")
def health():
    return {"chunks": conn.execute("SELECT count(*) FROM chunks").fetchone()[0]}
