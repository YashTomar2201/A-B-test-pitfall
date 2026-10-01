# A/B Pitfall Lab - Project Charter

## Problem
ShopKart, an Indian e-commerce app, runs about 40 A/B tests per quarter. Analysts use a plain t-test, check
results daily, and ship anything with p < 0.05 on any metric or segment. Leadership suspects many "wins"
do not hold up after launch, but nobody knows how many.

## Stakeholders (personas)
- **Head of Product**: wants to know how many shipped wins were real, and what the false ones cost
- **Growth PM**: wants faster tests without being wrong more often
- **Analytics Lead**: wants a standard checklist before any result is shared

## Key questions
1. How much does each common mistake (peeking, SRM, novelty, multiple testing, etc.) inflate false positives or bias effect estimates?
2. Which detection checks catch each mistake, and how reliably?
3. How much can variance reduction (CUPED) shorten tests?
4. Applied to a realistic portfolio of 40 tests, how many naive "wins" were false, and what did that cost?

## Scenario and metrics
One-page checkout redesign. Unit of randomisation: user. Default 50/50 split, 14 days.

| Type | Metric | Why |
|---|---|---|
| Primary | Conversion rate (0/1) | Binary metric; classic z-test |
| Secondary | Revenue per user (INR) | Heavy-tailed; shows outlier and CUPED effects |
| Secondary | Average order value | Ratio metric; delta method |
| Secondary | Clicks per session | Unit-of-analysis pitfall |
| Guardrail | Page load time, refund rate | Harm, not just wins |

## Success criteria
- Simulator passes A/A (false positive rate 5% +/- 1.5%) and known-effect (CI coverage 95% +/- 2%) tests
- Every pitfall module reports a Monte Carlo headline number and a verified fix
- Methods validated on a real randomized dataset (Criteo and Hillstrom), with Python and SQL results agreeing
- Deliverables: live Streamlit app, experimentation playbook, audit report, README

## Out of scope
Bandits, interference / network effects (listed as a limitation), Bayesian A/B testing, real company data.
