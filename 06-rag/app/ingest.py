"""Chunk the MedlinePlus snapshot, embed new or changed chunks and upsert them into pgvector.

Idempotent: each chunk carries a hash of its text and the embedding model, so a re-run only
embeds what changed and deletes chunks whose topic left the snapshot.
"""
import hashlib
import json

from common import CFG, check_ollama, connect, embed, to_vector

BATCH = 32


def chunk(topic):
    """Pack paragraphs up to max_chars; every chunk starts with the topic title so it stands alone."""
    header = topic["title"]
    if topic["also_called"]:
        header += f" (also called: {', '.join(topic['also_called'])})"
    chunks, current = [], ""
    for para in topic["summary"].split("\n\n"):
        if current and len(current) + len(para) > CFG["chunking"]["max_chars"]:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return [f"{header}\n\n{c}" for c in chunks]


rows = []
for line in open(CFG["snapshot"]["path"]):
    topic = json.loads(line)
    for n, content in enumerate(chunk(topic)):
        digest = hashlib.sha256(f"{CFG['embed_model']}\n{content}".encode()).hexdigest()
        rows.append({"id": f"{topic['id']}:{n}", "topic_id": topic["id"], "title": topic["title"],
                     "url": topic["url"], "chunk_no": n, "content": content, "content_hash": digest})

with connect() as conn:
    existing = dict(conn.execute("SELECT id, content_hash FROM chunks").fetchall())
    todo = [r for r in rows if existing.get(r["id"]) != r["content_hash"]]
    stale = existing.keys() - {r["id"] for r in rows}

    if todo:
        check_ollama()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        for row, vector in zip(batch, embed([r["content"] for r in batch], "document")):
            conn.execute(
                """INSERT INTO chunks (id, topic_id, title, url, chunk_no, content, content_hash, embedding)
                   VALUES (%(id)s, %(topic_id)s, %(title)s, %(url)s, %(chunk_no)s, %(content)s, %(content_hash)s,
                           %(embedding)s::vector)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, url = EXCLUDED.url,
                       content = EXCLUDED.content, content_hash = EXCLUDED.content_hash,
                       embedding = EXCLUDED.embedding""",
                {**row, "embedding": to_vector(vector)},
            )
        print(f"embedded {min(i + BATCH, len(todo))}/{len(todo)}", flush=True)
    if stale:
        conn.execute("DELETE FROM chunks WHERE id = ANY(%s)", (list(stale),))

    print(f"chunks: {len(rows)} total, {len(todo)} embedded, {len(rows) - len(todo)} unchanged, {len(stale)} deleted")
