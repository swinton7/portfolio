select
    reference as payment_id,
    settled_amount::decimal(18, 2) as settled_amount,
    fee::decimal(18, 2) as fee,
    settlement_date::date as settlement_date
from {{ ref('bronze_settlements') }}
