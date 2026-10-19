CREATE TABLE payments (
    id          SERIAL PRIMARY KEY,
    merchant_id TEXT           NOT NULL,
    amount      NUMERIC(12, 2) NOT NULL,
    status      TEXT           NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);

ALTER TABLE payments REPLICA IDENTITY FULL;

INSERT INTO payments (merchant_id, amount, status)
SELECT 'm_' || lpad((1 + i % 10)::TEXT, 4, '0'), round((random() * 5000 + 100)::NUMERIC, 2), 'paid'
FROM generate_series(1, 20) i;
