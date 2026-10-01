# Experiment audit

**Question:** ShopKart ran 40 A/B tests per quarter. How many shipped "wins" were real, and what did the false ones cost?

**Design:** 500 simulated quarters × 40 experiments = **20,000 experiments**, each with a known true effect. The scenario mix and economics are assumptions ([`config/audit_portfolio.yaml`](../config/audit_portfolio.yaml)). Two analysts decide on every experiment; every decision is scored against the truth.

## Results (median over quarters)
| | Naive | Rigorous |
|---|---|---|
| "Wins" shipped | 21 | 11 |
| False wins shipped | 9 | 2 |
| False discovery rate | 46% | 17% |
| True wins shipped | 11.0 | 9.0 |
| True wins not shipped | 3.0 | 4.0 |
| Average **reported** lift of shipped changes | 20.9% | 12.1% |
| Average **true** lift of shipped changes | 6.0% | 10.1% |

The naive analyst's reported lift is far above the true lift of what it ships (winner's curse at portfolio level).

## What each analyst ships, by what is really going on
| Scenario | Experiments | Naive ships | Rigorous ships |
|---|---|---|---|
| noisy revenue | 999 | 20% | 3% |
| novelty only | 2,056 | 100% | 35% |
| small win underpowered | 1,965 | 36% | 0% |
| srm bug | 1,995 | 40% | 0% |
| true null | 7,969 | 21% | 3% |
| true win | 5,016 | 98% | 93% |

Only `true win` and `small win underpowered` are real wins; everything else should not ship. The rigorous analyst's weak spot is `novelty only`: the novelty check detects only part of those cases.

## Cost (illustrative; rests on stated assumptions)
Assumptions (config `economics` block): 2,000,000 monthly users, 5% baseline conversion, ₹1,000 average order, 10% contribution margin, ₹5.0 lakh engineering cost per shipped change. A false win costs engineering time only (its true effect is zero). A true win flagged for rerun is a **delay** (3 months of its margin); a true win that is abandoned loses 12 months.

| Cost of one false win | Naive, median quarterly cost | Rigorous, median quarterly cost |
|---|---|---|
| ₹0 | ₹1.44 crore | ₹94.7 lakh |
| ₹5.0 lakh | ₹1.82 crore | ₹1.03 crore |
| ₹20.0 lakh | ₹3.32 crore | ₹1.42 crore |
| ₹50.0 lakh | ₹6.09 crore | ₹2.10 crore |

**Worst case for the rigorous analyst** (a flagged rerun is treated as an abandoned idea): naive ₹1.82 crore vs rigorous ₹2.78 crore median quarterly cost - the rigorous analyst costs MORE in this case, because it declines to ship underpowered true wins.

## Sensitivity to the share of true wins
| True-win share | Naive FDR | Rigorous FDR | Naive false wins | Rigorous false wins |
|---|---|---|---|---|
| 15% | 56% | 25% | 10 | 2 |
| 35% | 35% | 12% | 8 | 2 |

## Limitations
- The scenario shares and every cost figure are assumptions; the false discovery rates and reported-vs-true lift gaps do not depend on the cost assumptions.
- The rigorous analyst's power check turns underpowered true wins into "rerun" calls; whether that is a delay or a loss is a business judgement (see the worst case above).
- 500 quarters, not thousands: medians are stable but tails are not.
