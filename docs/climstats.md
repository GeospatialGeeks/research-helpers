# Climate time-series statistics (`research_helpers.climstats`)

Time-series statistics for climate and environmental data: climatology, anomalies, trends with honest uncertainty.

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

## Functions and classes

**`anomalies(series, base=None, freq='month', standardise=False)`**

Departure of each value from its climatology (see climatology()). With standardise=True, divided by the
standard deviation of the same calendar group in the base period (a z-score).

**`bootstrap_ci(values, statistic=<function mean at 0x0000017A536BA370>, n=2000, level=0.95, block=1, seed=0)`**

Percentile bootstrap interval for statistic(values). block > 1 resamples moving blocks of that length, which
keeps short-range dependence (use for time series). Returns (estimate, low, high).

**`climatology(series, base=None, freq='month')`**

Mean for each calendar month (freq='month'), day of year ('dayofyear') or season ('season': DJF, MAM, JJA, SON)
over the base period (start, end) given as anything pandas can slice by, e.g. ("1991", "2020").

**`mann_kendall(y)`**

Mann-Kendall test for a monotonic trend, with the variance corrected for ties. Returns S, z and the two-sided p.

Assumes independent values; for autocorrelated series pre-whiten first or read p as a lower bound.

**`sen_slope(x, y, per=1.0)`**

Theil-Sen slope: the median of all pairwise slopes. Resistant to outliers; pair with mann_kendall() for a test.

**`trend(x, y, per=1.0)`**

Least-squares trend of y on x, with its standard error corrected for lag-1 autocorrelation of the residuals.

per scales the slope (per=10 with x in years gives a trend per decade). Returns slope, se_naive, r1, n_eff,
se (corrected) and a 95% interval using Student's t with n_eff - 2 degrees of freedom (Santer et al. 2000).
NaNs are dropped. If r1 <= 0 no correction is made.
