-- dbt mart model example: merchant-level payment performance.

SELECT
    merchant_id,
    COUNT(*) AS total_payments,
    SUM(is_failed) AS failed_payments,
    AVG(payment_amount) AS avg_payment_amount,
    AVG(previous_failure_count) AS avg_previous_failure_count,
    AVG(CASE WHEN estimated_balance_band = 'low' THEN 1 ELSE 0 END) AS low_balance_share,
    1.0 * SUM(is_failed) / COUNT(*) AS failure_rate
FROM {{ ref('stg_payments') }}
GROUP BY merchant_id;
