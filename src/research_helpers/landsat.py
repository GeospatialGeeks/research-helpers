"""Landsat through time in Earth Engine, on one scale, for any project: land cover, snow, water.

    col = landsat.collection(region, 2000)              TM, ETM+ and OLI surface reflectance, harmonised to OLI
    table = landsat.availability(region, 1972, 2025)    clear scenes per year by sensor, to see what a period can support

Sensors and limits:
    MSS 1972-1992   60 m, four bands, no SWIR, no surface reflectance product: see mss(). Not comparable with later sensors
    TM  1984-2012   30 m. Coverage outside the USA is thin before about 1990 in many regions
    ETM+ 1999-2022  30 m. Line gaps after May 2003, and a drifting orbit late in life
    OLI 2013-       30 m, the reference scale here

Coefficients are Roy et al. (2016), fitted on top-of-atmosphere pairs in the USA. Check them locally with cross_sensor_check().
"""
import ee

COMMON = ["blue", "green", "red", "nir", "swir1", "swir2"]
ROY_SLOPE = [0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071]
ROY_INTERCEPT = [0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172]
SENSORS = {"LT04": ("LANDSAT/LT04/C02/T1_L2", 1982, 1993), "LT05": ("LANDSAT/LT05/C02/T1_L2", 1984, 2012), "LE07": ("LANDSAT/LE07/C02/T1_L2", 1999, 2022), "LC08": ("LANDSAT/LC08/C02/T1_L2", 2013, 2100), "LC09": ("LANDSAT/LC09/C02/T1_L2", 2021, 2100)}
MSS = {"LM01": "LANDSAT/LM01/C02/T2", "LM02": "LANDSAT/LM02/C02/T2", "LM03": "LANDSAT/LM03/C02/T2", "LM04": "LANDSAT/LM04/C02/T2", "LM05": "LANDSAT/LM05/C02/T2"}


def prepare(asset, region, start, end, harmonise=True, slope=None, intercept=None):
    """One sensor, cloud-screened, as surface reflectance named by colour. Snow is kept, because it is often the subject."""
    oli = "LC0" in asset
    bands = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"] if oli else ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"]
    sl, ic = slope or ROY_SLOPE, intercept or ROY_INTERCEPT

    def one(i):
        clear = i.select("QA_PIXEL").bitwiseAnd(0b11010).eq(0)
        sr = i.select(bands, COMMON).multiply(0.0000275).add(-0.2).updateMask(clear)
        sr = sr.updateMask(sr.gt(0).reduce(ee.Reducer.min()))
        if harmonise and not oli:
            sr = sr.multiply(ee.Image.constant(sl)).add(ee.Image.constant(ic)).rename(COMMON)
        return sr.toFloat().copyProperties(i, ["system:time_start"])
    return ee.ImageCollection(asset).filterBounds(region).filterDate(start, end).map(one)


def collection(region, year, months=(1, 12), harmonise=True, skip_etm_after=2012):
    """All sensors flying in a year, optionally for chosen months. ETM+ is left out once OLI flies, unless skip_etm_after is raised."""
    start, end = ee.Date.fromYMD(year, months[0], 1), ee.Date.fromYMD(year, months[1], 1).advance(1, "month")
    out = None
    for name, (asset, first, last) in SENSORS.items():
        if first <= year <= last and not (name == "LE07" and year > skip_etm_after):
            c = prepare(asset, region, start, end, harmonise)
            out = c if out is None else out.merge(c)
    if out is None:
        raise ValueError(f"no Landsat surface reflectance for {year}; before 1982 see mss()")
    return out


def mss(region, year, months=(1, 12)):
    """Landsat 1 to 5 MSS, 1972 to 1992: top-of-atmosphere-free digital numbers, with bands renamed. Use for visual or scene-level work."""
    start, end = ee.Date.fromYMD(year, months[0], 1), ee.Date.fromYMD(year, months[1], 1).advance(1, "month")
    out = None
    for name, asset in MSS.items():
        c = ee.ImageCollection(asset).filterBounds(region).filterDate(start, end)
        n = "B4" if name in ("LM01", "LM02", "LM03") else "B1"
        bn = ["B4", "B5", "B6", "B7"] if name in ("LM01", "LM02", "LM03") else ["B1", "B2", "B3", "B4"]
        c = c.select(bn, ["green", "red", "nir1", "nir2"])
        out = c if out is None else out.merge(c)
    return out


def availability(region, first=1972, last=2025):
    """Scenes per year by sensor for an area, read once from the catalogue."""
    rows = []
    both = {**{k: v[0] for k, v in SENSORS.items()}, **MSS}
    for name, asset in both.items():
        c = ee.ImageCollection(asset).filterBounds(region).filterDate(f"{first}-01-01", f"{last + 1}-01-01")
        hist = c.aggregate_histogram("DATE_ACQUIRED").getInfo()
        by = {}
        for d, n in hist.items():
            y = int(d[:4])
            by[y] = by.get(y, 0) + n
        rows += [dict(sensor=name, year=y, scenes=n) for y, n in by.items()]
    return rows


def cross_sensor_check(region, year=2016, a="LANDSAT/LE07/C02/T1_L2", b="LANDSAT/LC08/C02/T1_L2", scale=120):
    """Mean difference between two sensors' median composites, with and without harmonising."""
    s, e = f"{year}-01-01", f"{year + 1}-01-01"
    ref = prepare(b, region, s, e).median()
    out = {}
    for label, h in (("before", False), ("after", True)):
        d = prepare(a, region, s, e, h).median().subtract(ref).reduceRegion(ee.Reducer.mean(), region, scale, maxPixels=1e9, tileScale=8).getInfo()
        out[label] = {k: round(v, 4) for k, v in d.items()}
    return out
