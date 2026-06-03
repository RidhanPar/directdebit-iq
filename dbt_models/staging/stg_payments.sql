-- dbt staging model example.
-- In a real dbt project, replace source() with your configured source.

SELECT
    payment_id,
    merchant_id,
    customer_id,
    CAST(payment_amount AS FLOAT) AS payment_amount,
    currency,
    CAST(payment_date AS DATE) AS payment_date,
    payment_day_of_month,
    day_of_week,
    mandate_age_days,
    previous_failure_count,
    bank_country,
    bank_type,
    estimated_balance_band,
    days_since_last_success,
    payment_type,
    payment_status,
    CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END AS is_failed
FROM {{ source('directdebit_iq', 'payments') }};
