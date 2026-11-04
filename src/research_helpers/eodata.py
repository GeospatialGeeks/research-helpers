"""A second route to the satellite and climate data usually read through Google Earth Engine.

    from research_helpers import eodata
    eodata.routes("COPERNICUS/S2_SR_HARMONIZED")
    items = eodata.search("COPERNICUS/S2_SR_HARMONIZED", bbox, "2024-06-01/2024-06-30")
    cube = eodata.load("COPERNICUS/S2_SR_HARMONIZED", bbox, "2024-06-01/2024-06-30", bands=["B04"], crs="EPSG:27700", resolution=10)

    python -m research_helpers.eodata check     tries one small request on every route and writes a table

The same data from another archive is not always the same numbers: processing versions, scaling and cloud masks differ.
Use compare() on a small area against stored Earth Engine values before mixing the two in one analysis.
"""
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

PC = "https://planetarycomputer.microsoft.com/api/stac/v1"
AWS = "https://earth-search.aws.element84.com/v1"


@dataclass
class Route:
    kind: str                 # stac, earthaccess, url, cds or none
    where: str                # STAC address, NASA short name, or URL pattern
    collection: str = ""
    bands: dict = field(default_factory=dict)    # Earth Engine band: band at this route
    note: str = ""


S2_BANDS = {b: b for b in ("B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12", "SCL")}
S2_EE = {"B2": "B02", "B3": "B03", "B4": "B04", "B5": "B05", "B6": "B06", "B7": "B07", "B8": "B08", "B8A": "B8A", "B11": "B11", "B12": "B12", "SCL": "SCL"}
S2 = [Route("stac", PC, "sentinel-2-l2a", S2_EE, "Same ESA product. Earth Engine's harmonised version removes the 1000 offset added from January 2022, so check the offset."),
      Route("stac", AWS, "sentinel-2-l2a", {"B2": "blue", "B3": "green", "B4": "red", "B8": "nir", "B11": "swir16", "B12": "swir22", "SCL": "scl"}, "Second copy, on Amazon.")]
LANDSAT = [Route("stac", PC, "landsat-c2-l2", {"SR_B2": "blue", "SR_B3": "green", "SR_B4": "red", "SR_B5": "nir08", "SR_B6": "swir16", "SR_B7": "swir22", "QA_PIXEL": "qa_pixel"}, "Same USGS Collection 2 Level 2. Filter by platform.")]
ERA5 = [Route("cds", "reanalysis-era5-land", note="Needs a free key from the Copernicus Climate Data Store in ~/.cdsapirc."),
        Route("stac", PC, "era5-pds", note="Global ERA5 at about 31 km, not ERA5-Land at 9 km.")]
CATALOGUE = {
    "COPERNICUS/S2_SR_HARMONIZED": S2, "COPERNICUS/S2_SR": S2,
    "COPERNICUS/S1_GRD": [Route("stac", PC, "sentinel-1-rtc", {"VV": "vv", "VH": "vh"}, "Terrain-corrected and linear power, whereas Earth Engine holds dB without terrain flattening. Not interchangeable without compare()."),
                          Route("stac", PC, "sentinel-1-grd", {"VV": "vv", "VH": "vh"}, "Unprocessed GRD: calibration needed.")],
    "LANDSAT/LC08/C02/T1_L2": LANDSAT, "LANDSAT/LC09/C02/T1_L2": LANDSAT, "LANDSAT/LE07/C02/T1_L2": LANDSAT, "LANDSAT/LT05/C02/T1_L2": LANDSAT,
    "LANDSAT/LT05/C01/T1_SR": LANDSAT, "LANDSAT/LE07/C01/T1_SR": LANDSAT, "LANDSAT/LC08/C01/T1_SR": LANDSAT,
    "MODIS/061/MOD10A1": [Route("stac", PC, "modis-10A1-061", {"NDSI_Snow_Cover": "NDSI_Snow_Cover"}), Route("earthaccess", "MOD10A1", note="NASA NSIDC. Needs a free Earthdata login.")],
    "MODIS/061/MYD10A1": [Route("stac", PC, "modis-10A1-061", note="Filter platform to Aqua."), Route("earthaccess", "MYD10A1", note="NASA NSIDC. Needs a free Earthdata login.")],
    "MODIS/061/MOD10A2": [Route("stac", PC, "modis-10A2-061")],
    "MODIS/061/MCD12Q1": [Route("stac", PC, "modis-12Q1-061")],
    "MODIS/006/MOD11A1": [Route("stac", PC, "modis-11A1-061", note="Collection 6.1 replaces 6.")],
    "COPERNICUS/DEM/GLO30_2024_1": [Route("stac", PC, "cop-dem-glo-30")],
    "NASA/NASADEM_HGT/001": [Route("stac", PC, "nasadem")],
    "ESA/WorldCover/v200": [Route("stac", PC, "esa-worldcover")],
    "GOOGLE/DYNAMICWORLD/V1": [Route("none", "", note="No full copy elsewhere. Use io-lulc-annual-v02 or esa-worldcover as stand-ins, and report the change.")],
    "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS": [Route("stac", PC, "io-lulc-annual-v02")],
    "COPERNICUS/S5P/NRTI/L3_NO2": [Route("stac", PC, "sentinel-5p-l2-netcdf", note="Level 2 swaths: gridding is needed.")],
    "JRC/GSW1_4/GlobalSurfaceWater": [Route("stac", PC, "jrc-gsw")],
    "JRC/GSW1_0/GlobalSurfaceWater": [Route("stac", PC, "jrc-gsw", note="Newer version.")],
    "LARSE/GEDI/GEDI02_A_002_MONTHLY": [Route("earthaccess", "GEDI02_A", note="Footprint files; the monthly raster must be rebuilt.")],
    "LARSE/GEDI/GEDI04_B_002": [Route("earthaccess", "GEDI_L4B_Gridded_Biomass_V2_1_2299", note="ORNL DAAC.")],
    "ECMWF/ERA5_LAND/DAILY_AGGR": ERA5, "ECMWF/ERA5_LAND/MONTHLY_AGGR": ERA5,
    "NASA/GLDAS/V021/NOAH/G025/T3H": [Route("earthaccess", "GLDAS_NOAH025_3H", note="GES DISC.")],
    "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG": [Route("url", "https://eogdata.mines.edu/nighttime_light/monthly/v10/", note="Colorado School of Mines. Needs a free login.")],
    "JRC/GHSL/P2023A/GHS_BUILT_V/2020": [Route("url", "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_V_GLOBE_R2023A/")],
    "JRC/GHSL/P2023A/GHS_BUILT_H/2018": [Route("url", "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_H_GLOBE_R2023A/")],
    "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL": [Route("url", "https://source.coop/tge-labs/aef", note="Copy of the annual embeddings as cloud files.")],
    "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED": [Route("none", "", note="No copy elsewhere. Use SCL from sentinel-2-l2a, which masks clouds less strictly, and compare.")],
    "UK/EA/ENGLAND_1M_TERRAIN/2022": [Route("url", "https://environment.data.gov.uk/survey", note="Environment Agency LiDAR, as tiles.")],
    "MERIT/DEM/v1_0_3": [Route("url", "https://hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_DEM/", note="Needs a free registration.")],
    "JAXA/ALOS/PALSAR/YEARLY/SAR/2020": [Route("stac", PC, "alos-palsar-mosaic")],
    "UMD/hansen/global_forest_change_2018_v1_6": [Route("url", "https://storage.googleapis.com/earthenginepartners-hansen/", note="Direct files, newer versions alongside.")],
    "COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019": [Route("url", "https://land.copernicus.eu/en/products/global-dynamic-land-cover", note="Copernicus Land Service, and Zenodo record 3939050.")],
    "WWF/HydroSHEDS/v1/Basins/hybas_5": [Route("url", "https://www.hydrosheds.org/products/hydrobasins")],
    "GLIMS/current": [Route("url", "https://www.glims.org/download/")],
    "USDOS/LSIB_SIMPLE/2017": [Route("url", "https://geodata.state.gov/geonetwork/srv/eng/catalog.search", note="Or shared-geodata for boundaries used here.")],
}


def routes(gee_id):
    if gee_id not in CATALOGUE:
        raise KeyError(f"{gee_id} has no second route listed yet; add it to CATALOGUE")
    return CATALOGUE[gee_id]


def _client(route):
    import pystac_client
    return pystac_client.Client.open(route.where)


def _items(found, route):
    """Items from a search, under old and new versions of pystac-client, signed where the archive needs it."""
    items = found.items() if hasattr(found, "items") else found.get_items()
    if "planetarycomputer" not in route.where:
        return list(items)
    import planetary_computer
    return [planetary_computer.sign(x) for x in items]


def search(gee_id, bbox, datetime, route=0, **query):
    """STAC items for a bounding box in degrees (west, south, east, north) and a date range."""
    r = [x for x in routes(gee_id) if x.kind == "stac"][route]
    return _items(_client(r).search(collections=[r.collection], bbox=bbox, datetime=datetime, **query), r)


def load(gee_id, bbox, datetime, bands, crs, resolution, route=0, **query):
    """An xarray cube under the Earth Engine band names, read only for the box requested."""
    import odc.stac
    r = [x for x in routes(gee_id) if x.kind == "stac"][route]
    items = search(gee_id, bbox, datetime, route, **query)
    mapped = {b: r.bands.get(b, b) for b in bands}
    cube = odc.stac.load(items, bands=list(mapped.values()), bbox=bbox, crs=crs, resolution=resolution, chunks={})
    return cube.rename({v: k for k, v in mapped.items()})


def nasa_files(short_name, bbox, datetime, folder):
    """Download NASA granules with earthaccess. Needs a free Earthdata login."""
    import earthaccess
    earthaccess.login()
    found = earthaccess.search_data(short_name=short_name, bounding_box=tuple(bbox), temporal=tuple(datetime.split("/")))
    return earthaccess.download(found, str(folder))


def compare(a, b):
    """How far apart two aligned arrays are: pixels, bias, mean absolute difference and correlation."""
    import numpy as np
    a, b = np.asarray(a, float).ravel(), np.asarray(b, float).ravel()
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    return dict(n=int(ok.sum()), bias=float((b - a).mean()), mae=float(abs(b - a).mean()), r=float(np.corrcoef(a, b)[0, 1]))


def check(out="eodata_routes.csv", bbox=(-6.0, 54.55, -5.9, 54.65), when="2022-06-01/2022-06-30"):
    """Try each route with a small real request, and record what happened. Keys are not needed for the check."""
    import urllib.error
    import urllib.request
    rows, seen = [], {}
    for gee_id, rs in CATALOGUE.items():
        for r in rs:
            key = (r.kind, r.where, r.collection)
            if key not in seen:
                try:
                    if r.kind == "stac":
                        c = _client(r)
                        col = c.get_collection(r.collection)
                        n = len(_items(c.search(collections=[r.collection], bbox=bbox, max_items=3), r))
                        seen[key] = f"ok: collection found, {n} sample items" if n else "collection found, no items for the test place"
                        del col
                    elif r.kind == "url":
                        q = urllib.request.Request(r.where, headers={"User-Agent": "Mozilla/5.0"})
                        seen[key] = f"ok: address answers {urllib.request.urlopen(q, timeout=30).status}"
                    elif r.kind == "earthaccess":
                        import earthaccess
                        seen[key] = f"ok: {earthaccess.search_datasets(short_name=r.where, count=1)[0]['umm']['ShortName']} listed; login needed to download"
                    elif r.kind == "cds":
                        seen[key] = "not tested: needs a free key"
                    else:
                        seen[key] = "no second route"
                except urllib.error.HTTPError as e:
                    seen[key] = f"server is there, login needed: {e.code}" if e.code in (401, 403) else f"FAILED: {e.code}"
                except Exception as e:
                    seen[key] = f"FAILED: {type(e).__name__} {str(e)[:80]}"
            rows.append(dict(gee_id=gee_id, kind=r.kind, where=r.collection or r.where, result=seen[key], note=r.note))
            print(gee_id, "|", r.kind, r.collection or r.where, "|", seen[key], flush=True)
    with open(out, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


if __name__ == "__main__" and sys.argv[1:] == ["check"]:
    check(str(Path("eodata_routes.csv")))
