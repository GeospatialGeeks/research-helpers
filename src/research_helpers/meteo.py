"""Meteorology: moisture, stability, heights and winds, as functions that take numbers or NumPy arrays.

    from research_helpers import meteo
    meteo.dew_point_from_rh(25, 60)            # 16.7 deg C
    meteo.geostrophic_wind(60, 500e3, 55)      # m/s

Units are in each name or docstring: temperatures in deg C unless _k, pressures in hPa, mixing ratios in g/kg.
Gathered from the EGM305 atmosphere book (part3.py) and the atmosphere atlas (atlas/physics.py), which repeated the same
equations; both can import from here.

Sources
    Bolton, D. (1980) The computation of equivalent potential temperature. Mon. Wea. Rev. 108, 1046-1053.
        Saturation vapour pressure e_s = 6.112 exp(17.67 T / (T + 243.5)), within 0.1% for -30 to 35 deg C.
    Wallace, J.M. and Hobbs, P.V. (2006) Atmospheric Science, 2nd ed. Mixing ratio, hypsometric equation, geostrophic wind.
"""
import numpy as np

G = 9.81            # gravitational acceleration, m/s2
R_D = 287.0         # gas constant for dry air, J/(kg K)
EPS = 0.622         # ratio of the gas constants of dry air and water vapour; 622 when w is in g/kg
OMEGA = 7.292e-5    # Earth's angular velocity, rad/s
KNOT = 0.514444     # m/s in one knot (1852 m per hour)
DRY_LAPSE = 9.8     # dry adiabatic lapse rate, K/km


def saturation_vapour_pressure(t_c):
    """Saturation vapour pressure over water (hPa) at temperature t_c (deg C), by Bolton (1980).

    >>> round(saturation_vapour_pressure(20), 2)
    23.37
    """
    t = np.asarray(t_c, dtype=float)
    return 6.112 * np.exp(17.67 * t / (t + 243.5))


def mixing_ratio(e_hpa, p_hpa):
    """Mixing ratio (g/kg) from vapour pressure e and total pressure p: w = 622 e / (p - e)."""
    return 1000 * EPS * np.asarray(e_hpa, float) / (np.asarray(p_hpa, float) - e_hpa)


def saturation_mixing_ratio(t_c, p_hpa):
    """Saturation mixing ratio (g/kg) at temperature t_c (deg C) and pressure p_hpa."""
    return mixing_ratio(saturation_vapour_pressure(t_c), p_hpa)


def vapour_pressure(w_gkg, p_hpa):
    """Vapour pressure (hPa) from the mixing ratio (g/kg): the inverse of mixing_ratio()."""
    w = np.asarray(w_gkg, float)
    return w * p_hpa / (1000 * EPS + w)


def relative_humidity(w, w_s):
    """Relative humidity (%) as the ratio of mixing ratio to saturation mixing ratio (the textbook definition)."""
    return 100.0 * np.asarray(w, float) / w_s


def dew_point_from_e(e_hpa):
    """Dew point (deg C) from vapour pressure (hPa), by inverting Bolton's formula."""
    x = np.log(np.asarray(e_hpa, float) / 6.112)
    return 243.5 * x / (17.67 - x)


def dew_point(w_gkg, p_hpa):
    """Dew point (deg C) from mixing ratio (g/kg) and pressure (hPa)."""
    return dew_point_from_e(vapour_pressure(w_gkg, p_hpa))


def dew_point_from_rh(t_c, rh):
    """Dew point (deg C) from temperature (deg C) and relative humidity (%), taking RH = e / e_s.

    >>> round(float(dew_point_from_rh(25, 60)), 1)
    16.7
    """
    return dew_point_from_e(saturation_vapour_pressure(t_c) * np.asarray(rh, float) / 100)


def rh_rule_of_thumb(t_c, t_d):
    """Approximate relative humidity (%): 100 - 5 (T - Td). Good to a few percent above about 50% RH (Lawrence 2005)."""
    return 100.0 - 5.0 * (np.asarray(t_c, float) - t_d)


def cloud_base(t_c, t_d):
    """Approximate height of the base of convective cloud (m above the surface): 125 m per degree of dew-point depression.

    Air rises at the dry lapse rate (9.8 K/km) while its dew point falls about 1.8 K/km, closing the gap at 8 K/km."""
    return 125.0 * (np.asarray(t_c, float) - t_d)


def thickness(mean_t_k, p1_hpa, p2_hpa):
    """Hypsometric equation: thickness (m) of the layer from p1 (lower, larger) to p2, mean temperature in K.

    >>> round(float(thickness(273.15, 1000, 500)))
    5539
    """
    return R_D * np.asarray(mean_t_k, float) / G * np.log(np.asarray(p1_hpa, float) / p2_hpa)


def coriolis_parameter(lat_deg):
    """Coriolis parameter f = 2 Omega sin(latitude), per second. Zero at the equator, negative in the south."""
    return 2.0 * OMEGA * np.sin(np.radians(lat_deg))


def geostrophic_wind(dz_m, dn_m, lat_deg):
    """Geostrophic wind speed (m/s) from the height change dz of a pressure surface over a distance dn: (g/f) dz/dn.

    Not defined near the equator, where f tends to zero; values within about 10 degrees of it are not meaningful."""
    return G / coriolis_parameter(lat_deg) * np.asarray(dz_m, float) / dn_m


def fahrenheit_to_celsius(t_f):
    """Temperature (deg C) from deg F."""
    return (np.asarray(t_f, float) - 32.0) * 5.0 / 9.0


def kelvin_to_celsius(t_k):
    """Temperature (deg C) from kelvin."""
    return np.asarray(t_k, float) - 273.15


def knots_to_ms(knots):
    """Wind speed (m/s) from knots, with the exact knot of 1852 m per hour."""
    return KNOT * np.asarray(knots, float)


def decode_pressure(code):
    """Sea-level pressure (hPa) from the three-digit code on a station model: 1000 + code/10 below 500, else 900 + code/10.

    >>> decode_pressure(132), decode_pressure(978)
    (1013.2, 997.8)
    """
    return (1000.0 if code < 500 else 900.0) + code / 10.0


def wind_components(speed, direction_deg):
    """Eastward u and northward v (same units as speed) from speed and the direction the wind blows FROM (degrees)."""
    d = np.radians(direction_deg)
    return -np.asarray(speed, float) * np.sin(d), -np.asarray(speed, float) * np.cos(d)


def wind_speed_direction(u, v):
    """Speed and the direction the wind blows FROM (degrees, 0 = north) from u and v: the inverse of wind_components()."""
    return np.hypot(u, v), np.degrees(np.arctan2(-np.asarray(u, float), -np.asarray(v, float))) % 360
