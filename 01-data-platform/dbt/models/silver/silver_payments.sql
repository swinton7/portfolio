select
    payment_id,
    merchant_id,
    (amount / 100)::decimal(18, 2) as amount,
    currency,
    method,
    status,
    created_at,
    created_at::date as created_date
from {{ ref('bronze_payments') }}
qualify row_number() over (partition by payment_id order by created_at desc) = 1
