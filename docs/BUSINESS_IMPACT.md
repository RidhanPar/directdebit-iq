# Business Impact Analysis

> **Scenario notice:** every financial value in this memo is an illustrative scenario built from synthetic data and stated assumptions. It is not observed production benefit, a forecast, or a guarantee.

## Executive Summary

DirectDebit IQ predicts high-risk payment failures before collection, allowing operations teams to intervene earlier, optimise retry timing, and prioritise the payments most likely to create revenue leakage. The current model uses customer payment history, mandate age, merchant-level risk, bank geography, balance band, and temporal patterns to produce a failure probability for each scheduled payment. At the selected operating threshold of 0.30, the model reaches **94.5% recall**, meaning it captures most known failure cases in the test set, with **0.690 ROC-AUC** and **0.296 average precision**.

Using a monthly scenario of **1,000,000 transactions**, an average transaction value of **£150**, and a fraud/high-risk loss rate of **0.17%**, DirectDebit IQ can flag approximately **1,606 high-risk transactions per month** before they become confirmed losses. After allowing for false-positive review/friction costs, the modelled net monthly benefit is approximately **£216,512**, with payback possible inside the first quarter under the implementation assumptions below. These figures should be treated as a business-case estimate, not a production guarantee, because real benefit depends on merchant mix, retry policy, customer communications, and operational capacity.

## Problem Statement

Payment failures create a direct revenue gap and an indirect operational cost. Common causes include insufficient funds, closed or invalid bank accounts, and disputed payments. GoCardless explains that Direct Debit payments can fail for multiple operational and customer-account reasons, including insufficient funds and invalid or closed bank accounts. Bottomline estimates recovery costs can reach **£50–£100 per failed payment**, while older Bacs-linked commentary has cited repair costs up to **£50 per failed Direct Debit**. For this portfolio business model, we use a more conservative direct operational assumption of **£5–£25 per failure** and a **£3 false-positive handling/friction cost**.

Current detection approaches often rely on static rules such as “flag customers with more than N previous failures” or “avoid retrying on specific days.” These rules are easy to understand, but they become brittle when customer behaviour, bank patterns, fraud tactics, or merchant portfolios change. Rule-based systems also struggle to combine weak signals across many dimensions, for example a new mandate, low balance band, Monday collection, and a merchant with elevated historical failures.

Machine learning outperforms simple rule-based systems when the decision depends on many interacting signals. A model can learn non-linear relationships, update from new data, rank payments by probability of failure, and support risk-based operations rather than binary “block/allow” logic. However, ML should complement—not fully replace—business rules: rules remain useful for compliance, hard eligibility constraints, and explainable escalation policies.

## Solution Performance

| Metric | Industry Baseline | Our Model | Improvement |
|---|---:|---:|---:|
| ROC-AUC | 0.500 random/static baseline | 0.690 | +19.0 percentage points |
| Recall at action threshold | 60.0% rule-based benchmark | 94.5% | +34.5 percentage points |
| Precision at action threshold | 12.0% rule-based benchmark | 16.5% | +4.5 percentage points |
| F1 score at threshold 0.30 | 0.200 benchmark | 0.281 | +40.3% relative uplift |
| Average precision | 0.170 class-rate baseline | 0.296 | +74.2% relative uplift |
| Revenue at risk caught per 1,000 predictions | £35,000 benchmark | £59,092 | +68.8% relative uplift |

**Interpretation:** DirectDebit IQ is tuned for early warning and operational recovery. The threshold of 0.30 deliberately prioritises recall over precision because the business cost of missing a genuine high-risk payment can be higher than the cost of reviewing or retrying a legitimate payment.

## Financial Impact Modelling

### Assumptions

| Assumption | Value | Notes |
|---|---:|---|
| Monthly transactions | 1,000,000 | Enterprise-scale merchant portfolio |
| Average transaction value | £150 | Blended recurring payment value |
| Fraud/high-risk loss rate | 0.17% | Business-case scenario requested for modelling |
| High-risk transactions per month | 1,700 | 1,000,000 × 0.17% |
| Model recall | 94.5% | Actual test-set result at threshold 0.30 |
| Model precision | 16.5% | Actual test-set result at threshold 0.30 |
| False-positive handling/friction cost | £3 per case | Conservative operating assumption |
| One-time implementation cost | £120,000 | Data integration, monitoring, governance, release |
| Monthly operating cost | £15,000 | Hosting, monitoring, model review, support |

### Monthly Benefit Calculation

| Calculation | Formula | Result |
|---|---|---:|
| Gross revenue exposure | 1,000,000 × 0.17% × £150 | £255,000 |
| Revenue protected per month | 1,700 × 94.5% × £150 | £240,939 |
| Predicted positive cases | 1,606 ÷ 16.5% precision | 9,749 |
| False positives | Predicted positives − true positives caught | 8,142 |
| Cost of false positives | 8,142 × £3 | £24,427 |
| **Net benefit per month** | Revenue protected − false-positive cost | **£216,512** |

### ROI Projection

| Time Horizon | Gross Benefit | Total Cost | Net Value | ROI |
|---|---:|---:|---:|---:|
| 3 months | £649,537 | £165,000 | £484,537 | 294% |
| 6 months | £1,299,073 | £210,000 | £1,089,073 | 519% |
| 12 months | £2,598,146 | £300,000 | £2,298,146 | 766% |

**Sensitivity note:** If operational teams choose a stricter threshold, false positives will reduce but some failures will be missed. If the business chooses a more aggressive threshold, recall may improve but review volume and customer-friction costs will increase. The final threshold should be selected through A/B testing and capacity-aware monitoring.

## Operational Impact

- **Reduction in manual review cases:** Instead of reviewing broad rule-triggered populations, analysts can focus on ranked high-risk payments with the largest expected value at risk. This supports better queue prioritisation and reduces wasted effort on low-value cases.
- **Faster payment processing:** Low-risk payments can pass through with less intervention, while high-risk payments receive targeted retry or customer-contact actions before collection failure occurs.
- **Customer trust improvement:** Early detection enables proactive communication, smarter retry timing, and fewer repeated failed-payment experiences. This reduces avoidable friction for customers and gives merchants clearer visibility into expected cash flow.
- **Better merchant conversations:** Merchant-level risk scores help account teams identify where failures are concentrated, for example by merchant, bank country, mandate age, or payment day.
- **Repeatable analytics workflow:** MLflow tracking, SQL analytics, Streamlit dashboards, and Docker support make the project reproducible for technical and business review.

## Limitations & Risks

- **Model drift over time:** Failure patterns may change as merchants, banks, customer behaviour, and macroeconomic conditions change. The model requires scheduled monitoring and retraining.
- **Adversarial fraud patterns:** Fraud behaviour can adapt when controls become predictable. The model should be paired with anomaly detection, fraud rules, and human review feedback loops.
- **Data quality dependencies:** Missing payment history, inconsistent merchant IDs, delayed failure labels, or incorrect mandate-age data can reduce prediction quality.
- **False-positive customer friction:** Aggressive risk thresholds may delay legitimate payments or create unnecessary customer contact. Thresholds must be tuned against both financial benefit and customer experience.
- **Synthetic-data limitation:** The current project is built on synthetic data. Production validation must be completed using real historical payment outcomes before business decisions are automated.

## Recommended Next Steps

1. **Validate on real historical payment data** across multiple merchants, bank countries, payment types, and time periods. Confirm whether the synthetic-data signal transfers to production data.
2. **Run a champion/challenger test** comparing the ML model against existing rules using the same operational capacity and the same review budget.
3. **Run the implemented action API in shadow mode** and compare its recommendations with actual analyst decisions before enabling operational execution.
4. **Create an A/B testing framework for retry strategies** to measure whether recommended retry dates increase recovery rates without increasing customer complaints.
5. **Extend the implemented governance baseline** with data drift, performance drift, retraining cadence, alert thresholds, privacy review, and rollback procedures.

## External Context Used

- [GoCardless guidance on why bank debit payments fail](https://gocardless.com/en-us/guides/posts/why-bank-debit-payments-fail/), including insufficient funds and invalid or closed bank accounts.
- [Bottomline commentary on taking control of Direct Debit failures](https://www.bottomline.com/resources/blog/taking-control-direct-debit-failures).
- [Bottomline commentary on the hidden cost of payment failures](https://www.bottomline.com/newsroom/events/hidden-cost-payment-failures-and-how-solve-them).
- Fraud and payment-risk industry commentary explaining that machine learning can adapt better than static rules, while still requiring validation, monitoring, and governance.
