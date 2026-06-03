-- Failure behaviour by estimated balance band and previous failure history.
SELECT
    estimated_balance_band,
    previous_failure_count,
    COUNT(*) AS total_payments,
    ROUND(AVG(payment_amount), 2) AS avg_payment_amount,
    SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failed_payments,
    ROUND(1.0 * SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 4) AS failure_rate
FROM payments
GROUP BY estimated_balance_band, previous_failure_count
ORDER BY
    CASE estimated_balance_band
        WHEN 'low' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'high' THEN 3
        ELSE 4
    END,
    previous_failure_count;
