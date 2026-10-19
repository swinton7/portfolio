{{ config(location='s3://lake/gold/reconciliation.parquet') }}

with paid as (
    select * from {{ ref('silver_payments') }} where status = 'paid'
)

select
    coalesce(p.payment_id, s.payment_id) as payment_id,
    p.merchant_id,
    p.created_date,
    p.amount as expected_amount,
    s.settled_amount,
    s.fee,
    s.settlement_date,
    case
        when s.payment_id is null then 'missing_settlement'
        when p.payment_id is null then 'orphan_settlement'
        when p.amount <> s.settled_amount then 'amount_mismatch'
        else 'matched'
    end as match_status
from paid p
full outer join {{ ref('silver_settlements') }} s on p.payment_id = s.payment_id
