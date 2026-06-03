/*
DirectDebit IQ — Monthly Payment Success Rates

Purpose:
- Track the monthly trend in payment success and failure volume.
- Compare each month against the previous month using a window function.
- This query is useful for executive reporting, monitoring payment health,
  and identifying months where payment performance dropped.
*/

WITH monthly_summary AS (
    /*
    Step 1: Aggregate payments by year-month.
    SQLite stores payment_date as TEXT in ISO format, so strftime('%Y-%m', ...)
    safely extracts a sortable month key.
    */
    SELECT
        strftime('%Y-%m', payment_date) AS year_month,
        COUNT(*) AS total_payments,
        SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) AS successful_payments,
        SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failed_payments,
        ROUND(
            100.0 * SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) / COUNT(*),
            2
        ) AS success_rate_pct
    FROM payments
    GROUP BY strftime('%Y-%m', payment_date)
),
monthly_with_previous AS (
    /*
    Step 2: Use LAG to bring the previous month's success rate into the
    current row. This allows month-over-month comparison in the final output.
    */
    SELECT
        year_month,
        total_payments,
        successful_payments,
        failed_payments,
        success_rate_pct,
        LAG(success_rate_pct) OVER (ORDER BY year_month) AS previous_month_success_rate_pct
    FROM monthly_summary
)

/*
Step 3: Return the monthly trend and calculate the percentage-point change
versus the previous month. The first month has no previous comparison, so it
returns NULL for vs_previous_month_change.
*/
SELECT
    year_month,
    total_payments,
    successful_payments,
    failed_payments,
    success_rate_pct,
    ROUND(success_rate_pct - previous_month_success_rate_pct, 2) AS vs_previous_month_change
FROM monthly_with_previous
ORDER BY year_month;
