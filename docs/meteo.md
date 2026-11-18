# Meteorology equations (`research_helpers.meteo`)

Meteorology: moisture, stability, heights and winds, as functions that take numbers or NumPy arrays.

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

## Functions and classes

**`cloud_base(t_c, t_d)`**

Approximate height of the base of convective cloud (m above the surface): 125 m per degree of dew-point depression.

Air rises at the dry lapse rate (9.8 K/km) while its dew point falls about 1.8 K/km, closing the gap at 8 K/km.

**`coriolis_parameter(lat_deg)`**

Coriolis parameter f = 2 Omega sin(latitude), per second. Zero at the equator, negative in the south.

**`decode_pressure(code)`**

Sea-level pressure (hPa) from the three-digit code on a station model: 1000 + code/10 below 500, else 900 + code/10.

>>> decode_pressure(132), decode_pressure(978)
(1013.2, 997.8)

**`dew_point(w_gkg, p_hpa)`**

Dew point (deg C) from mixing ratio (g/kg) and pressure (hPa).

**`dew_point_from_e(e_hpa)`**

Dew point (deg C) from vapour pressure (hPa), by inverting Bolton's formula.

**`dew_point_from_rh(t_c, rh)`**

Dew point (deg C) from temperature (deg C) and relative humidity (%), taking RH = e / e_s.

>>> round(float(dew_point_from_rh(25, 60)), 1)
16.7

**`fahrenheit_to_celsius(t_f)`**

Temperature (deg C) from deg F.

**`geostrophic_wind(dz_m, dn_m, lat_deg)`**

Geostrophic wind speed (m/s) from the height change dz of a pressure surface over a distance dn: (g/f) dz/dn.

Not defined near the equator, where f tends to zero; values within about 10 degrees of it are not meaningful.

**`kelvin_to_celsius(t_k)`**

Temperature (deg C) from kelvin.

**`knots_to_ms(knots)`**

Wind speed (m/s) from knots, with the exact knot of 1852 m per hour.

**`mixing_ratio(e_hpa, p_hpa)`**

Mixing ratio (g/kg) from vapour pressure e and total pressure p: w = 622 e / (p - e).

**`relative_humidity(w, w_s)`**

Relative humidity (%) as the ratio of mixing ratio to saturation mixing ratio (the textbook definition).

**`rh_rule_of_thumb(t_c, t_d)`**

Approximate relative humidity (%): 100 - 5 (T - Td). Good to a few percent above about 50% RH (Lawrence 2005).

**`saturation_mixing_ratio(t_c, p_hpa)`**

Saturation mixing ratio (g/kg) at temperature t_c (deg C) and pressure p_hpa.

**`saturation_vapour_pressure(t_c)`**

Saturation vapour pressure over water (hPa) at temperature t_c (deg C), by Bolton (1980).

>>> round(saturation_vapour_pressure(20), 2)
23.37

**`thickness(mean_t_k, p1_hpa, p2_hpa)`**

Hypsometric equation: thickness (m) of the layer from p1 (lower, larger) to p2, mean temperature in K.

>>> round(float(thickness(273.15, 1000, 500)))
5539

**`vapour_pressure(w_gkg, p_hpa)`**

Vapour pressure (hPa) from the mixing ratio (g/kg): the inverse of mixing_ratio().

**`wind_components(speed, direction_deg)`**

Eastward u and northward v (same units as speed) from speed and the direction the wind blows FROM (degrees).

**`wind_speed_direction(u, v)`**

Speed and the direction the wind blows FROM (degrees, 0 = north) from u and v: the inverse of wind_components().
