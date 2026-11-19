"""Known values for meteo and indices, worked by hand or taken from the cited sources."""
import math
import numpy as np
from research_helpers import indices, meteo


def test_saturation_vapour_pressure():
    """Saturation vapour pressure: 6.112 hPa at 0 deg C (Bolton 1980)."""
    assert abs(meteo.saturation_vapour_pressure(0) - 6.112) < 1e-9          # Bolton's constant at 0 deg C
    assert abs(meteo.saturation_vapour_pressure(20) - 23.37) < 0.01         # tables: 23.39


def test_dew_point_round_trip():
    """Dew point of saturated air gives back its temperature."""
    w = meteo.saturation_mixing_ratio(15, 1000)
    assert abs(meteo.dew_point(w, 1000) - 15) < 1e-9                        # saturated air: dew point = temperature
    assert abs(meteo.dew_point_from_rh(25, 60) - 16.69) < 0.02


def test_thickness_and_wind():
    """Hypsometric thickness, Coriolis parameter, geostrophic wind and wind components against hand values."""
    assert abs(meteo.thickness(273.15, 1000, 500) - 287 * 273.15 / 9.81 * math.log(2)) < 1e-6
    assert abs(meteo.coriolis_parameter(30) - 7.292e-5) < 1e-12              # sin 30 = 1/2
    assert abs(meteo.geostrophic_wind(60, 500e3, 30) - 9.81 / 7.292e-5 * 60 / 500e3) < 1e-9
    u, v = meteo.wind_components(10, 270)                                    # westerly: blows towards the east
    assert abs(u - 10) < 1e-9 and abs(v) < 1e-9
    s, d = meteo.wind_speed_direction(u, v)
    assert abs(s - 10) < 1e-9 and abs(d - 270) < 1e-9


def test_codes_and_units():
    """Station pressure codes and unit conversions."""
    assert meteo.decode_pressure(132) == 1013.2 and meteo.decode_pressure(978) == 997.8
    assert abs(meteo.knots_to_ms(1) - 1852 / 3600) < 1e-6
    assert meteo.fahrenheit_to_celsius(212) == 100


def test_indices():
    """Spectral indices against hand values."""
    assert indices.ndvi(0.5, 0.1) == 0.4 / 0.6
    assert np.isnan(indices.ndvi(0.0, 0.0))
    assert abs(indices.evi(0.5, 0.1, 0.05) - 2.5 * 0.4 / (0.5 + 0.6 - 0.375 + 1)) < 1e-12
    assert abs(indices.savi(0.5, 0.1) - 1.5 * 0.4 / 1.1) < 1e-12
    bands = {"B8": np.array([0.5]), "B4": np.array([0.1])}
    assert indices.compute("ndvi", bands)[0] == 0.4 / 0.6


def test_climstats():
    """Climate statistics (anomalies, trends) on series with known answers."""
    import pandas as pd
    from research_helpers import climstats as cs
    idx = pd.date_range("2000-01-01", periods=48, freq="MS")
    s = pd.Series(np.tile(np.arange(12.0), 4) + 1, index=idx)               # same cycle every year
    assert np.allclose(cs.anomalies(s), 0)
    x = np.arange(30.0)
    t = cs.trend(x, 2 * x + 1, per=10)
    assert abs(t["slope"] - 20) < 1e-9
    assert cs.sen_slope(x, 2 * x) == 2 and cs.sen_slope([0, 1, 2, 3], [0, 1, 100, 3]) == 1
    mk = cs.mann_kendall(np.arange(10.0))
    assert mk["S"] == 45 and mk["p"] < 0.001                                 # every pair increases: S = n(n-1)/2
    est, lo, hi = cs.bootstrap_ci(np.arange(100.0))
    assert est == 49.5 and lo < 49.5 < hi
    rng = np.random.default_rng(1)
    e = np.zeros(200)
    for i in range(1, 200):
        e[i] = 0.7 * e[i - 1] + rng.normal()                                 # AR(1): corrected SE must be larger
    t = cs.trend(np.arange(200.0), e)
    assert t["r1"] > 0.5 and t["se"] > 1.5 * t["se_naive"]


def test_rasters():
    """Slope and aspect of a tilted plane, and other raster helpers, against hand values."""
    from research_helpers import rasters as rs
    x, y = np.meshgrid(np.arange(10.0), np.arange(10.0))
    dem = 10 * x                                    # rises 10 m per 10 m cell to the east: 45 degrees, faces west
    s, a = rs.slope_aspect(dem, 10)
    assert abs(s[5, 5] - 45) < 1e-9 and abs(a[5, 5] - 270) < 1e-9
    s, a = rs.slope_aspect(10 * y, 10)              # rises to the south: faces north
    assert abs(a[5, 5] % 360) < 1e-9
    assert rs.local_relief(dem, 3)[5, 5] == 20
    assert np.allclose(rs.to_linear(rs.to_db(np.array([0.5, 2.0]))), [0.5, 2.0])
    assert abs(rs.mean_db(np.array([[0.0], [10.0]]))[0] - 10 * np.log10(5.5)) < 1e-9
    flat = np.random.default_rng(0).gamma(4.4, 1 / 4.4, (64, 64))
    assert rs.lee_filter(flat).std() < flat.std() / 2
    lab = np.array([[1, 1, 2], [1, 0, 2]])
    v = np.array([[1.0, 3.0, np.nan], [5.0, 9.0, 4.0]])
    z = rs.zonal(v, lab, min_valid=0.6)
    assert z["mean"][1] == 3 and z["median"][1] == 3 and np.isnan(z["mean"][2]) and z["valid_share"][2] == 0.5


def test_code_fingerprint_ignores_documentation_only():
    """Fingerprints ignore docstrings and comments but change with code."""
    from research_helpers.inventory import code_fingerprint
    a = "def f(x):\n    return x + 1\n"
    b = '"""Module."""\ndef f(x):\n    """Add one."""\n    # a comment\n    return x + 1\n'
    c = "def f(x):\n    return x + 2\n"
    assert code_fingerprint(a) == code_fingerprint(b) != code_fingerprint(c)
