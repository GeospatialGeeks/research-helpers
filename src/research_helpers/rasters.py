"""Rasters: reading and writing GeoTIFFs, terrain, SAR backscatter, lidar heights and zonal statistics.

    from research_helpers import rasters as rs
    a, prof = rs.read("dem.tif")                 # float array with NaN for no-data, and the rasterio profile
    rs.write("relief.tif", rs.local_relief(a, 67), prof)
    slope, aspect = rs.slope_aspect(a, prof["transform"].a)
    rs.zonal(a, labels)                          # mean, median, count per label
    db = rs.to_db(linear); rs.mean_db(stack_db)  # SAR: average in power, not in decibels
    ndsm = rs.ndsm(dsm, dtm)                     # lidar height above ground

Gathered from kkh-hazard (relief, terrain), sar-reading-manual (sarlib.py) and the PhD (lidar heights, zonal statistics).
Needs NumPy and SciPy; read() and write() need rasterio. Every function works on plain arrays, so it can be tested and
reused without files.

Sources
    Horn, B.K.P. (1981) Hill shading and the reflectance map. Proc. IEEE 69(1), 14-47: slope from a 3 x 3 window.
    Lee, J.-S. (1980) IEEE Trans. Pattern Anal. Mach. Intell. 2(2), 165-168: speckle filter.
    Haralick, R.M. et al. (1973) IEEE Trans. Syst. Man Cybern. 3(6), 610-621: texture from co-occurrence matrices.
"""
import numpy as np


# ---------------------------------------------------------------- files

def read(path, band=1):
    """One band as float64 with no-data set to NaN, and the rasterio profile (CRS, transform, size) for writing back."""
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(band).astype(float)
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        return a, src.profile.copy()


def write(path, array, profile, nodata=-9999.0, keep_old=True):
    """Write a float32 GeoTIFF, compressed and tiled, NaN written as nodata. Earlier versions are archived with
    safeio.keep() unless keep_old=False."""
    import rasterio
    from .safeio import keep
    a = np.where(np.isfinite(array), array, nodata).astype("float32")
    p = dict(profile, driver="GTiff", dtype="float32", count=1 if a.ndim == 2 else a.shape[0], nodata=nodata,
             compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    dest = keep(path) if keep_old else path
    with rasterio.open(dest, "w", **p) as dst:
        dst.write(a, 1) if a.ndim == 2 else dst.write(a)
    return dest


def stretch(a, low=2, high=98):
    """Scale to 0-1 between two percentiles, for display only (never for analysis)."""
    lo, hi = np.nanpercentile(a, [low, high])
    return np.clip((a - lo) / (hi - lo), 0, 1)


# ---------------------------------------------------------------- terrain

def slope_aspect(dem, cell, cell_y=None):
    """Slope (degrees) and aspect (degrees clockwise from north, the way the slope faces) by Horn's 3 x 3 method.

    dem in metres on a projected grid with square cells of size cell (m); north is up (row 0 is the northern edge).
    Edges are NaN. Agrees with GDAL's gdaldem slope and aspect to within 0.001 degrees (checked on a test surface)."""
    cy = cell_y or cell
    z = np.pad(np.asarray(dem, float), 1, constant_values=np.nan)
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell)          # rises to the east
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cy)            # rises to the south
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = np.degrees(np.arctan2(-dzdx, dzdy)) % 360               # downslope direction, from north
    return slope, aspect


def local_relief(dem, size):
    """Highest minus lowest elevation in a size x size window around each cell (kkh-hazard used 67 cells, about 2 km
    at 30 m). No-data cells stay NaN and do not count."""
    from scipy.ndimage import maximum_filter, minimum_filter
    a = np.asarray(dem, float)
    m = ~np.isfinite(a)
    hi = maximum_filter(np.where(m, -np.inf, a), size)
    lo = minimum_filter(np.where(m, np.inf, a), size)
    return np.where(m, np.nan, hi - lo)


def hillshade(dem, cell, azimuth=315, altitude=45):
    """Shaded relief 0-1 for a light source at azimuth (degrees from north) and altitude (degrees above horizon)."""
    s, asp = slope_aspect(dem, cell)
    s, asp = np.radians(s), np.radians(asp)
    z, az = np.radians(90 - altitude), np.radians(azimuth)
    return np.clip(np.cos(z) * np.cos(s) + np.sin(z) * np.sin(s) * np.cos(az - asp), 0, 1)


# ---------------------------------------------------------------- SAR

def to_db(linear):
    """Backscatter in decibels from linear power: 10 log10(x). Zero and negative values give NaN."""
    x = np.asarray(linear, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(x > 0, 10 * np.log10(x), np.nan)


def to_linear(db):
    """Linear power from decibels: 10^(dB/10)."""
    return 10 ** (np.asarray(db, float) / 10)


def mean_db(stack_db, axis=0):
    """Average a stack of dB images in linear power and return dB. Averaging decibels directly gives the geometric
    mean, which understates bright targets (by about 2.5 dB for fully developed speckle)."""
    return to_db(np.nanmean(to_linear(stack_db), axis=axis))


def lee_filter(power, size=7, looks=4.4):
    """Lee speckle filter on linear power. looks is the equivalent number of looks (about 4.4 for Sentinel-1 IW GRD).

    Each pixel moves towards the local mean by a weight that is small in flat areas (speckle) and near one at edges."""
    from scipy.ndimage import uniform_filter
    x = np.asarray(power, float)
    mean = uniform_filter(x, size)
    var = np.maximum(uniform_filter(x * x, size) - mean ** 2, 0)
    noise = mean ** 2 / looks                                       # speckle variance for L looks: (mean^2) / L
    w = np.clip((var - noise) / np.where(var > 0, var, np.nan), 0, 1)
    return mean + np.nan_to_num(w) * (x - mean)


def glcm_features(band, levels=32, distance=1, props=("contrast", "homogeneity", "energy", "correlation")):
    """Haralick texture of a whole image or window: band is rescaled to `levels` grey levels between its 1st and 99th
    percentiles, co-occurrence counted at `distance` in four directions and averaged. Needs scikit-image."""
    from skimage.feature import graycomatrix, graycoprops
    lo, hi = np.nanpercentile(band, [1, 99])
    q = np.clip((np.nan_to_num(band, nan=lo) - lo) / (hi - lo) * (levels - 1), 0, levels - 1).astype(np.uint8)
    m = graycomatrix(q, [distance], [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], levels=levels, symmetric=True, normed=True)
    return {p: float(graycoprops(m, p).mean()) for p in props}


# ---------------------------------------------------------------- lidar and zones

def ndsm(dsm, dtm, floor=0.0):
    """Normalised surface model: height above ground = DSM - DTM, with values below `floor` set to it."""
    return np.maximum(np.asarray(dsm, float) - dtm, floor)


def zonal(values, labels, min_valid=0.0, stats=("mean", "median", "count")):
    """Statistics of `values` within each integer label (0 = no zone), e.g. building heights within footprints.

    Returns a dict of arrays indexed by label, and the share of each zone's cells that were valid. Zones whose valid
    share is below min_valid get NaN (the PhD used 0.5 for lidar heights per footprint)."""
    v = np.asarray(values, float).ravel()
    lab = np.asarray(labels).ravel().astype(int)
    n = lab.max() + 1
    total = np.bincount(lab, minlength=n)
    ok = np.isfinite(v) & (lab > 0)
    cnt = np.bincount(lab[ok], minlength=n)
    share = np.divide(cnt, total, out=np.zeros(n), where=total > 0)
    out = {"valid_share": share}
    if "count" in stats:
        out["count"] = cnt
    if "mean" in stats:
        out["mean"] = np.divide(np.bincount(lab[ok], v[ok], minlength=n), cnt, out=np.full(n, np.nan), where=cnt > 0)
    if "median" in stats:
        med = np.full(n, np.nan)
        order = np.lexsort((v[ok], lab[ok]))
        sl, sv = lab[ok][order], v[ok][order]
        starts = np.searchsorted(sl, np.arange(n))
        for k in np.nonzero(cnt)[0]:
            med[k] = np.median(sv[starts[k]:starts[k] + cnt[k]])
        out["median"] = med
    for k in list(out):
        if k not in ("valid_share", "count"):
            out[k] = np.where(share >= min_valid, out[k], np.nan)
    return out
