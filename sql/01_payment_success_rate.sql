-- Payment success and failure rate by date, currency, and payment type.
SELECT
    payment_date,
    currency,
    payment_type,
    COUNT(*) AS total_payments,
    SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) AS successful_payments,
    SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failed_payments,
    ROUND(1.0 * SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 4) AS success_rate,
    ROUND(1.0 * SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 4) AS failure_rate
FROM payments
GROUP BY payment_date, currency, payment_type
ORDER BY payment_date DESC, total_payments DESC;
