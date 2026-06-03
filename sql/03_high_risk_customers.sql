/*
DirectDebit IQ — High-Risk Customer Identification

Purpose:
- Identify customers with repeated payment failures.
- Calculate a risk score using both failure rate and failure frequency.
- Only customers with 3+ payments are included to avoid overreacting to very
  small sample sizes.
*/

WITH customer_payment_summary AS (
    /*
    Step 1: Aggregate payment history at customer level.
    */
    SELECT
        customer_id,
        COUNT(*) AS total_payments,
        SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failure_count,
        SUM(CASE WHEN payment_status = 'failed' THEN payment_amount ELSE 0 END) AS total_amount_failed
    FROM payments
    GROUP BY customer_id
    HAVING COUNT(*) >= 3
),
customer_risk AS (
    /*
    Step 2: Calculate failure rate and risk score.
    Risk score formula:
      failure_rate * log(failure_count + 1)
    where failure_rate is represented as a decimal between 0 and 1.
    */
    SELECT
        customer_id,
        total_payments,
        failure_count,
        ROUND(1.0 * failure_count / total_payments, 4) AS failure_rate,
        ROUND(total_amount_failed, 2) AS total_amount_failed,
        ROUND((1.0 * failure_count / total_payments) * LOG(failure_count + 1), 4) AS risk_score
    FROM customer_payment_summary
)

/*
Step 3: Convert the numeric risk score into clear business categories.
Thresholds are intentionally simple so analysts can explain them easily.
*/
SELECT
    customer_id,
    total_payments,
    failure_count,
    failure_rate,
    total_amount_failed,
    risk_score,
    CASE
        WHEN risk_score >= 0.35 THEN 'CRITICAL'
        WHEN risk_score >= 0.20 THEN 'HIGH'
        WHEN risk_score >= 0.08 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_category
FROM customer_risk
ORDER BY risk_score DESC, failure_count DESC, total_amount_failed DESC;
