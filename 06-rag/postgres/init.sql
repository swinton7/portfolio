CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id           text PRIMARY KEY,
    topic_id     text NOT NULL,
    title        text NOT NULL,
    url          text NOT NULL,
    chunk_no     int  NOT NULL,
    content      text NOT NULL,
    content_hash text NOT NULL,
    embedding    vector(768) NOT NULL,
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
