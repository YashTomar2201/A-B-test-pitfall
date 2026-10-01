# Resume bullets (numbers read from the results)

**A/B Pitfall Lab** | Python, SQL (DuckDB), statsmodels, Streamlit · [Live app] · [GitHub]

- Built an experimentation simulation lab quantifying **9 common A/B-testing pitfalls** across 100K+ Monte Carlo simulations; showed daily peeking inflates false positives from **5% to 21.9%** and implemented O'Brien-Fleming and mSPRT sequential tests that restore validity (mSPRT at a cost of ~2.0x sample).
- Validated methods on **real randomized data (Criteo, 14.0M rows; Hillstrom)** with SQL (DuckDB) and Python cross-checked to the last digit; real-data A/A tests gave 4.8% false positives; found that covariate adjustment cut required sample by **26%** on Criteo visits and flagged a covariate imbalance between Criteo's arms that shifts the effect estimate.
- Designed a 7-check experiment health checker and audited **20,000 simulated experiments** with known ground truth: a naive process had a **46% false discovery rate** among shipped wins vs **17%** with the checker. Deployed as an interactive app.
