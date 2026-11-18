"""Time-series statistics for climate and environmental data: climatology, anomalies, trends with honest uncertainty.

    from research_helpers import climstats as cs
    anom = cs.anomalies(series, base=("1991", "2020"))            # pandas Series with a DatetimeIndex
    cs.trend(years, values)                                        # OLS slope, with SE corrected for autocorrelation
    cs.sen_slope(years, values); cs.mann_kendall(values)          # robust slope and its test
    cs.bootstrap_ci(values, np.median)                            # percentile interval for any statistic

Collected from the climate guides on the website, warming-trends-check, south-asia-monsoon and south-asia-smog,
which each had their own version.

Sources
    Santer, B.D. et al. (2000) J. Geophys. Res. 105(D6), 7337-7356: effective sample size n_eff = n (1 - r1)/(1 + r1).
    Sen, P.K. (1968) J. Am. Stat. Assoc. 63, 1379-1389. Mann (1945) Econometrica 13, 245-259; Kendall (1975).
    Efron, B. and Tibshirani, R. (1993) An Introduction to the Bootstrap. Moving blocks: Kunsch (1989) Ann. Stat. 17.
"""
import math

import numpy as np


def climatology(series, base=None, freq="month"):
    """Mean for each calendar month (freq='month'), day of year ('dayofyear') or season ('season': DJF, MAM, JJA, SON)
    over the base period (start, end) given as anything pandas can slice by, e.g. ("1991", "2020")."""
    s = series.loc[base[0]:base[1]] if base else series
    return s.groupby(_key(s.index, freq)).mean()


def anomalies(series, base=None, freq="month", standardise=False):
    """Departure of each value from its climatology (see climatology()). With standardise=True, divided by the
    standard deviation of the same calendar group in the base period (a z-score)."""
    s = series.loc[base[0]:base[1]] if base else series
    k = _key(series.index, freq)
    g = s.groupby(_key(s.index, freq))
    out = series - g.mean().reindex(k).to_numpy()
    if standardise:
        out = out / g.std().reindex(k).to_numpy()
    return out


def _key(index, freq):
    """Calendar group of each time stamp."""
    if freq == "month":
        return index.month
    if freq == "dayofyear":
        return index.dayofyear
    if freq == "season":
        return np.array(["DJF", "DJF", "MAM", "MAM", "MAM", "JJA", "JJA", "JJA", "SON", "SON", "SON", "DJF"])[index.month - 1]
    raise ValueError(freq)


def trend(x, y, per=1.0):
    """Least-squares trend of y on x, with its standard error corrected for lag-1 autocorrelation of the residuals.

    per scales the slope (per=10 with x in years gives a trend per decade). Returns slope, se_naive, r1, n_eff,
    se (corrected) and a 95% interval using Student's t with n_eff - 2 degrees of freedom (Santer et al. 2000).
    NaNs are dropped. If r1 <= 0 no correction is made."""
    from scipy import stats
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = len(y)
    fit = stats.linregress(x, y)
    resid = y - (fit.intercept + fit.slope * x)
    r1 = float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if n > 3 else 0.0
    n_eff = n * (1 - r1) / (1 + r1) if r1 > 0 else n
    se = fit.stderr * math.sqrt((n - 2) / max(n_eff - 2, 1))           # inflate the variance by (n - 2)/(n_eff - 2)
    t = stats.t.ppf(0.975, max(n_eff - 2, 1))
    return {"slope": fit.slope * per, "intercept": fit.intercept, "se_naive": fit.stderr * per, "r1": r1, "n": n,
            "n_eff": n_eff, "se": se * per, "lo": (fit.slope - t * se) * per, "hi": (fit.slope + t * se) * per}


def sen_slope(x, y, per=1.0):
    """Theil-Sen slope: the median of all pairwise slopes. Resistant to outliers; pair with mann_kendall() for a test."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    i, j = np.triu_indices(len(x), 1)
    dx = x[j] - x[i]
    keep = dx != 0
    return float(np.median((y[j] - y[i])[keep] / dx[keep])) * per


def mann_kendall(y):
    """Mann-Kendall test for a monotonic trend, with the variance corrected for ties. Returns S, z and the two-sided p.

    Assumes independent values; for autocorrelated series pre-whiten first or read p as a lower bound."""
    from scipy import stats
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    n = len(y)
    i, j = np.triu_indices(n, 1)
    s = float(np.sign(y[j] - y[i]).sum())
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - (counts * (counts - 1) * (2 * counts + 5)).sum()) / 18
    z = 0.0 if s == 0 else (s - np.sign(s)) / math.sqrt(var)          # continuity correction
    return {"S": s, "z": z, "p": float(2 * stats.norm.sf(abs(z)))}


def bootstrap_ci(values, statistic=np.mean, n=2000, level=0.95, block=1, seed=0):
    """Percentile bootstrap interval for statistic(values). block > 1 resamples moving blocks of that length, which
    keeps short-range dependence (use for time series). Returns (estimate, low, high)."""
    v = np.asarray(values)
    rng = np.random.default_rng(seed)
    m = len(v)
    if block <= 1:
        draws = [statistic(v[rng.integers(0, m, m)]) for _ in range(n)]
    else:
        starts = np.arange(m - block + 1)
        k = math.ceil(m / block)
        draws = [statistic(np.concatenate([v[s:s + block] for s in rng.choice(starts, k)])[:m]) for _ in range(n)]
    a = (1 - level) / 2
    return float(statistic(v)), float(np.quantile(draws, a)), float(np.quantile(draws, 1 - a))
