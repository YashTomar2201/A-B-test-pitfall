"""User-level experiment simulator with a known ground truth and switchable pitfalls."""
from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit


@dataclass
class ExperimentConfig:
    days: int = 14
    users_per_day: int = 4_000
    treat_share: float = 0.5
    base_cr: float = 0.05               # control conversion rate
    lift: float = 0.0                   # TRUE long-run relative lift on conversion
    novelty_boost: float = 0.0          # extra relative lift on day 0 that decays away
    novelty_halflife: float = 3.0       # days
    engagement_beta: float = 0.8        # how strongly latent engagement drives conversion
    rev_mu: float = 6.5                 # log-normal order value: exp(6.5) ~ Rs 665 median
    rev_sigma: float = 1.0
    pre_corr: float = 0.6               # corr(engagement now, engagement in pre-period)
    whale_rate: float = 0.0             # share of converters who are whales
    whale_multiplier: float = 50.0
    srm_drop_rate: float = 0.0          # share of treatment users lost (low-engagement ones)
    ramp_days: int = 0                  # days at reduced treatment share (Simpson's paradox)
    ramp_treat_share: float = 0.1
    n_segments: int = 5
    daily_base_cr: tuple | None = None  # optional per-day baseline (overrides base_cr)
    seed: int | None = None

    def with_(self, **kw) -> "ExperimentConfig":
        return replace(self, **kw)


@lru_cache(maxsize=512)
def _intercept(base_cr: float, beta: float) -> float:
    """Logit intercept so the AVERAGE conversion rate equals base_cr."""
    z = np.random.default_rng(12345).standard_normal(200_000)
    return brentq(lambda a: expit(a + beta * z).mean() - base_cr, -20, 10)


def simulate(cfg: ExperimentConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed)
    n = cfg.days * cfg.users_per_day
    day = np.repeat(np.arange(cfg.days), cfg.users_per_day)

    share = np.where(day < cfg.ramp_days, cfg.ramp_treat_share, cfg.treat_share)
    treat = rng.random(n) < share

    u = rng.standard_normal(n)                                    # latent engagement
    pre_latent = cfg.pre_corr * u + np.sqrt(1 - cfg.pre_corr**2) * rng.standard_normal(n)
    pre_spend = np.exp(cfg.rev_mu + cfg.rev_sigma * pre_latent)    # CUPED covariate

    lift_t = cfg.lift + cfg.novelty_boost * 0.5 ** (day / cfg.novelty_halflife)

    if cfg.daily_base_cr is None:
        a = _intercept(cfg.base_cr, cfg.engagement_beta)
    else:
        if len(cfg.daily_base_cr) != cfg.days:
            raise ValueError("daily_base_cr must have one entry per day")
        a = np.array([_intercept(float(b), cfg.engagement_beta) for b in cfg.daily_base_cr])[day]
    p0 = expit(a + cfg.engagement_beta * u)
    p = np.clip(p0 * (1 + treat * lift_t), 0, 1)
    converted = rng.random(n) < p

    order_latent = 0.5 * u + np.sqrt(0.75) * rng.standard_normal(n)
    revenue = np.where(converted, np.exp(cfg.rev_mu + cfg.rev_sigma * order_latent), 0.0)
    whale = converted & (rng.random(n) < cfg.whale_rate)
    revenue = np.where(whale, revenue * cfg.whale_multiplier, revenue)

    df = pd.DataFrame({
        "user_id": np.arange(n),
        "day": day,
        "arm": np.where(treat, "treatment", "control"),
        "segment": rng.integers(0, cfg.n_segments, n),
        "pre_spend": pre_spend,
        "converted": converted.astype(int),
        "revenue": revenue,
    })

    # SRM bug: the new page loses some LOW-engagement treatment users before logging.
    if cfg.srm_drop_rate > 0:
        lost = treat & (u < 0) & (rng.random(n) < 2 * cfg.srm_drop_rate)
        df = df[~lost].reset_index(drop=True)
    return df
