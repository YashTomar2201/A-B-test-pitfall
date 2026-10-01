# Decision Log

Running record of choices, surprises and dead ends. Newest last.

## Scenario and defaults
- **E-commerce checkout** chosen because it gives binary (conversion), heavy-tailed (revenue) and ratio (AOV, CTR) metrics in one scenario.
- **14-day default duration**: two full weekly cycles, so day-of-week effects cancel and novelty has time to fade.
- **alpha = 0.05 two-sided, power = 0.80**: industry defaults.
- **SRM threshold p < 0.001**, not 0.05: the check runs on every experiment, so a strict threshold keeps false alarms rare (following Fabijan et al. 2019).

## Simulator
- **Why simulate at all**: a false positive rate can only be measured when the true answer is known. Real experiments never reveal it. The simulator is therefore validated (A/A false positive rate, flat p-values, known-effect recovery, CI coverage) before any pitfall result is trusted, and the methods are separately checked on real randomized data.
- **Conversion model**: latent engagement `u ~ N(0,1)` drives conversion through a logistic link; the intercept is solved numerically so the *average* conversion rate equals `base_cr`. The treatment multiplies the conversion probability by `(1 + lift)`.
- **One outcome per user** (not a daily panel). Novelty is modelled as an extra lift that decays with calendar day since launch. This is a simplification; a real user-level novelty effect decays with *exposure* time.
- **Revenue** is log-normal order value for converters; treatment changes conversion only, so revenue lift comes from conversion.
- **SRM bug model**: the treatment arm loses low-engagement users (`u < 0`) before logging. This biases the treatment *upward*, which is the dangerous direction.
- **Binary-metric Monte Carlo uses aggregate counts** (`simulate/fast.py`): binomial counts per arm per day are sufficient statistics for the z-test, so results match the user-level engine but run roughly 100x faster.
- **Calibration**: baseline conversion 5% (round number for readability); Hillstrom's control conversion is only 0.57% and its log order value has mu = 4.44, sigma = 0.82, so the default simulator is *not* a Hillstrom clone. It is calibrated for shape (log-normal revenue, sparse conversion), not level.

## Peeking / sequential testing
- The O'Brien-Fleming constant is **calibrated by simulation** instead of looked up, and sanity-checked against the published value (about 2.04 for 5 looks; the calibration returned 2.042).
- **mSPRT is conservative at a fixed horizon.** With 14 discrete looks, the always-valid p-value cost roughly twice the sample for the same power (see `p1_msprt_cost.csv`). This is reported as a cost, not hidden; the benefit is that the number of looks does not need to be planned.
- `tau` (the mixing prior's standard deviation) is a tuning choice. Results are shown across a grid (`p1_msprt_tau.csv`), and 0.005 (about the size of the expected effect) is used for the cost study.

## Real data
- **Hillstrom** (64,000 customers, 3 arms) is the small real dataset: used for CUPED and calibration.
- **Criteo Uplift v2.1** (13,979,592 rows, 85% treated). Criteo's original download link now returns 404; the file was fetched from Criteo's own organisation repository on Hugging Face (311,422,618 bytes).
- **Dead end: sampling Criteo.** I first downloaded a 10% prefix of the file to save bandwidth. It contained *no control rows at all*, because the file is sorted by treatment. A second attempt (evenly spaced blocks of row groups) produced samples where every block was entirely treated or entirely control, with standardized covariate differences up to 0.08. Both were discarded. **Lesson: this file must be used whole;** the loader's docstring says so.
- **Randomization check on the full file**: the treatment share is 0.8500001 (clean SRM result), but pre-treatment features still differ between arms by up to 0.049 SD, versus about 0.0005 expected from randomization alone. A joint covariate adjustment moves the visit effect from +1.03 pp to +0.70 pp, which is about 27 standard errors. I cannot determine whether this comes from the public release or from how the features were built, so both estimates are reported and the cause is not asserted.
- **First covariate-adjustment attempt was wrong**: I estimated theta from a regression that omitted the treatment indicator, which is invalid when arms are imbalanced. It was replaced by a joint regression (outcome ~ treatment + covariates) with HC1 standard errors.
- **Hillstrom CUPED does almost nothing** (variance removed: 0.04%; corr(past spend, spend) = 0.02). Reported as is: CUPED helps only with a predictive covariate.

## Health checker
- **Balance check added** after the Criteo finding: standardized mean differences on pre-treatment covariates, with a Bonferroni-corrected critical value at p = 0.001.
- **Novelty check is deliberately strict** (one-sided p < 0.01 and a positive first-half minus second-half gap) to keep false alarms low; the cost is that it detects only part of the novelty cases. The report card quantifies this (see `checker_report_card.csv`).

## Audit
- **Scenario mix is an assumption.** Practitioner sources (e.g. Kohavi et al.) report that most experiment ideas do not improve their target metric, so a minority of true wins is realistic. The default is 25% clearly true wins plus 10% small underpowered true wins. Re-run at 15% and 35% as a sensitivity check.
- **Cost model**: a false win costs engineering time only (its true effect is zero in these scenarios). A true win the rigorous analyst *flags for rerun* is a delay (3 months of that lift's margin); a true win anyone *abandons* costs 12 months. **The result is sensitive to this**, so the audit reports (a) a sweep over the cost of a false win and (b) a worst case where a rerun is treated as an abandoned idea.
- **Quarter count**: the first attempt used 12 worker processes and crashed with `MemoryError` (machine has 7.3 GB RAM). The audit now defaults to 4 workers, 500 quarters of 40 experiments and 150 quarters per sensitivity case.
- All money figures are illustrative assumptions, not measurements.
