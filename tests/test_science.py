"""Known values for meteo and indices, worked by hand or taken from the cited sources."""
import math
import numpy as np
from research_helpers import indices, meteo


def test_saturation_vapour_pressure():
    assert abs(meteo.saturation_vapour_pressure(0) - 6.112) < 1e-9          # Bolton's constant at 0 deg C
    assert abs(meteo.saturation_vapour_pressure(20) - 23.37) < 0.01         # tables: 23.39


def test_dew_point_round_trip():
    w = meteo.saturation_mixing_ratio(15, 1000)
    assert abs(meteo.dew_point(w, 1000) - 15) < 1e-9                        # saturated air: dew point = temperature
    assert abs(meteo.dew_point_from_rh(25, 60) - 16.69) < 0.02


def test_thickness_and_wind():
    assert abs(meteo.thickness(273.15, 1000, 500) - 287 * 273.15 / 9.81 * math.log(2)) < 1e-6
    assert abs(meteo.coriolis_parameter(30) - 7.292e-5) < 1e-12              # sin 30 = 1/2
    assert abs(meteo.geostrophic_wind(60, 500e3, 30) - 9.81 / 7.292e-5 * 60 / 500e3) < 1e-9
    u, v = meteo.wind_components(10, 270)                                    # westerly: blows towards the east
    assert abs(u - 10) < 1e-9 and abs(v) < 1e-9
    s, d = meteo.wind_speed_direction(u, v)
    assert abs(s - 10) < 1e-9 and abs(d - 270) < 1e-9


def test_codes_and_units():
    assert meteo.decode_pressure(132) == 1013.2 and meteo.decode_pressure(978) == 997.8
    assert abs(meteo.knots_to_ms(1) - 1852 / 3600) < 1e-6
    assert meteo.fahrenheit_to_celsius(212) == 100


def test_indices():
    assert indices.ndvi(0.5, 0.1) == 0.4 / 0.6
    assert np.isnan(indices.ndvi(0.0, 0.0))
    assert abs(indices.evi(0.5, 0.1, 0.05) - 2.5 * 0.4 / (0.5 + 0.6 - 0.375 + 1)) < 1e-12
    assert abs(indices.savi(0.5, 0.1) - 1.5 * 0.4 / 1.1) < 1e-12
    bands = {"B8": np.array([0.5]), "B4": np.array([0.1])}
    assert indices.compute("ndvi", bands)[0] == 0.4 / 0.6
