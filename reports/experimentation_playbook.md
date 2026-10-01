# ShopKart Experimentation Rules (v1)

_One page for product managers. Each rule comes from a measured result in this project; the numbers are in `pitfall_summary.md`._

1. **Pick ONE primary metric before launch, and write it down.** Checking many metrics, or slicing into segments afterwards, almost guarantees a false win.
2. **Run a power calculation first.** If the test needs more than about 4 weeks, rethink the minimum detectable effect. Underpowered tests exaggerate the effects they do find.
3. **Run at least 2 full weeks, even if the result looks significant earlier.** New things look good for a few days; the lift often fades.
4. **Want to check early? Use the sequential dashboard, not the regular p-value.** Stopping on the first p < 0.05 inflates false positives several-fold.
5. **If the sample-ratio check is red, the result is invalid.** Stop and find out why users went missing. Do not look at the lift.
6. **Segment results are ideas for the next test, not reasons to ship.**
7. **Use CUPED on every metric with pre-period data, but check the correlation first.** A strong covariate shortens tests; a weak one does nothing.
8. **Analyse at the unit you randomised.** Users randomised means users analysed, not sessions.
9. **A test that was ramped up during a sale or campaign needs a day-stratified analysis.**
10. **Before shipping, run the health checker.** Ship only on a clean pass; a yellow means investigate, a red means rerun.

## What the health checker's colours mean
| Colour | Meaning | What to do |
|---|---|---|
| Green | Check passed | Nothing |
| Yellow | Result may still be right but is at risk (low power, novelty trend, outlier sensitivity, multiple comparisons) | Investigate or rerun longer |
| Red | The result cannot be trusted (SRM, peeking without a sequential method, unbalanced arms) | Fix the cause and rerun |
