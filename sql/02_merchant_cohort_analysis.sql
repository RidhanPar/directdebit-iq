/*
DirectDebit IQ — Merchant Cohort Analysis

Purpose:
- Group payment performance by merchant and mandate age band.
- Identify merchant + mandate-age combinations with weaker payment success.
- New mandates often carry higher operational risk, so this cohort view helps
  payment teams prioritize intervention.
*/

WITH payment_cohorts AS (
    /*
    Step 1: Assign each payment into a mandate age cohort.
    The bands are designed to separate very new mandates from mature mandates.
    */
    SELECT
        merchant_id,
        CASE
            WHEN mandate_age_days BETWEEN 0 AND 30 THEN '0-30 days'
            WHEN mandate_age_days BETWEEN 31 AND 90 THEN '31-90 days'
            WHEN mandate_age_days BETWEEN 91 AND 365 THEN '91-365 days'
            ELSE '365+ days'
        END AS mandate_age_band,
        payment_status
    FROM payments
),
cohort_summary AS (
    /*
    Step 2: Aggregate each merchant/cohort pair into payment counts and
    successful payment counts.
    */
    SELECT
        merchant_id,
        mandate_age_band,
        COUNT(*) AS payment_count,
        SUM(CASE WHEN payment_status = 'success' THEN 1 ELSE 0 END) AS successful_payments,
        SUM(CASE WHEN payment_status = 'failed' THEN 1 ELSE 0 END) AS failed_payments
    FROM payment_cohorts
    GROUP BY merchant_id, mandate_age_band
)

/*
Step 3: Return success rate by merchant and mandate age band.
The ordering puts the highest-failure cohorts near the top while still showing
high-volume cohorts first when failure rates are similar.
*/
SELECT
    merchant_id,
    mandate_age_band,
    payment_count,
    ROUND(100.0 * successful_payments / payment_count, 2) AS success_rate
FROM cohort_summary
ORDER BY success_rate ASC, payment_count DESC, merchant_id, mandate_age_band;
