/*
DirectDebit IQ — Bank Country and Bank Type Analysis

Purpose:
- Compare success rates across bank countries and bank types.
- Show average payment value by banking segment.
- Use a window function to identify the most common failure day for each
  bank_country + bank_type segment.
*/

WITH segment_summary AS (
    /*
    Step 1: Calculate payment volume, success rate, and average payment amount
    for each bank country and bank type.
    */
    SELECT
        bank_country,
        bank_type,
        COUNT(*) AS total_payments,
        ROUND(
            100.0 * SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) / COUNT(*),
            2
        ) AS success_rate,
        ROUND(AVG(payment_amount), 2) AS avg_payment_amount
    FROM payments
    GROUP BY bank_country, bank_type
),
failure_day_counts AS (
    /*
    Step 2: Count failures by day of week within each banking segment.
    */
    SELECT
        bank_country,
        bank_type,
        day_of_week,
        COUNT(*) AS failed_payments_on_day
    FROM payments
    WHERE payment_status = 'failed'
    GROUP BY bank_country, bank_type, day_of_week
),
ranked_failure_days AS (
    /*
    Step 3: Rank failure days inside each bank_country + bank_type segment.
    ROW_NUMBER keeps exactly one top day per segment. The CASE expression gives
    deterministic ordering when two days have the same failure count.
    */
    SELECT
        bank_country,
        bank_type,
        day_of_week,
        failed_payments_on_day,
        ROW_NUMBER() OVER (
            PARTITION BY bank_country, bank_type
            ORDER BY
                failed_payments_on_day DESC,
                CASE day_of_week
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    WHEN 'Sunday' THEN 7
                    ELSE 8
                END
        ) AS day_rank
    FROM failure_day_counts
)

/*
Step 4: Join segment-level payment performance with the top failure day.
*/
SELECT
    s.bank_country,
    s.bank_type,
    s.total_payments,
    s.success_rate,
    s.avg_payment_amount,
    COALESCE(r.day_of_week, 'No failures') AS most_common_failure_day
FROM segment_summary s
LEFT JOIN ranked_failure_days r
    ON s.bank_country = r.bank_country
    AND s.bank_type = r.bank_type
    AND r.day_rank = 1
ORDER BY s.success_rate ASC, s.total_payments DESC, s.bank_country, s.bank_type;
