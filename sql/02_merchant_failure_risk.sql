-- Top merchants by payment failure risk.
SELECT
    merchant_id,
    COUNT(*) AS total_payments,
    SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failed_payments,
    ROUND(AVG(payment_amount), 2) AS avg_payment_amount,
    ROUND(AVG(previous_failure_count), 2) AS avg_previous_failure_count,
    ROUND(1.0 * SUM(CASE WHEN estimated_balance_band = 'low' THEN 1 ELSE 0 END) / COUNT(*), 4) AS low_balance_share,
    ROUND(1.0 * SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 4) AS failure_rate
FROM payments
GROUP BY merchant_id
HAVING COUNT(*) >= 100
ORDER BY failure_rate DESC, total_payments DESC
LIMIT 25;
