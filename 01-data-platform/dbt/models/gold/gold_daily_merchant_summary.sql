{{ config(location='s3://lake/gold/daily_merchant_summary.parquet') }}

select
    created_date,
    merchant_id,
    count(*) as payment_count,
    count(*) filter (where status = 'paid') as paid_count,
    sum(amount) filter (where status = 'paid') as paid_amount,
    round(count(*) filter (where status = 'paid') / count(*), 4) as success_rate
from {{ ref('silver_payments') }}
group by all
