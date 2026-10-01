"""P8 - Wrong unit of analysis (randomise by user, analyse by session)."""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit, logit

from abtest.analyze.tests import delta_method_ratio


def simulate_sessions(rng, n_users=6_000, mean_sessions=5, base_ctr=0.10, user_sd=1.0, lift=0.0):
    sessions = 1 + rng.poisson(mean_sessions - 1, n_users)
    treat = rng.random(n_users) < 0.5
    p = np.clip(expit(logit(base_ctr) + user_sd * rng.standard_normal(n_users)) * (1 + lift * treat), 0, 1)
    clicks = rng.binomial(sessions, p)
    return treat, sessions, clicks


def unit_of_analysis_fpr(user_sd_grid=(0.0, 0.5, 1.0, 1.5, 2.0), n_sims=1_500, seed=0, **kw) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for sd in user_sd_grid:
        naive = correct = 0
        for _ in range(n_sims):
            t, s, c = simulate_sessions(rng, user_sd=sd, **kw)
            ca, na, cb, nb = c[~t].sum(), s[~t].sum(), c[t].sum(), s[t].sum()
            pa, pb, pool = ca / na, cb / nb, (ca + cb) / (na + nb)
            z = (pb - pa) / np.sqrt(pool * (1 - pool) * (1 / na + 1 / nb))
            naive += abs(z) > stats.norm.ppf(0.975)
            correct += delta_method_ratio(c[~t], s[~t], c[t], s[t]).significant
        rows.append({"user_sd": sd, "naive_session_level_fpr": naive / n_sims,
                     "delta_method_fpr": correct / n_sims})
    return pd.DataFrame(rows)
