"""Spectral indices from surface reflectance, for NumPy arrays, xarray objects or Earth Engine images.

    from research_helpers import indices
    ndvi = indices.ndvi(nir, red)                         # arrays or DataArrays of reflectance (0-1)
    img = indices.add_ee(image, ["ndvi", "ndwi"], sensor="landsat_oli")   # Earth Engine: adds bands named NDVI, NDWI

Reflectance must be scaled to 0-1 first (Landsat Collection 2 Level 2: x 0.0000275 - 0.2; Sentinel-2 L2A: / 10000,
less 0.1 for products from January 2022 that are not harmonised). Indices that use constants (EVI, SAVI) are wrong on
unscaled digital numbers; normalised differences are not, but scale anyway so every index is on one footing.

Each index lists its source. The band each one needs, by sensor, is in BANDS.
"""
import numpy as np

# Band names by sensor for the generic roles used below.
BANDS = {
    "landsat_oli": {"blue": "SR_B2", "green": "SR_B3", "red": "SR_B4", "nir": "SR_B5", "swir1": "SR_B6", "swir2": "SR_B7"},
    "landsat_tm": {"blue": "SR_B1", "green": "SR_B2", "red": "SR_B3", "nir": "SR_B4", "swir1": "SR_B5", "swir2": "SR_B7"},
    "sentinel2": {"blue": "B2", "green": "B3", "red": "B4", "nir": "B8", "swir1": "B11", "swir2": "B12"},
}


def nd(a, b):
    """Normalised difference (a - b) / (a + b); NaN where a + b is zero."""
    if not hasattr(a, "dims"):                 # plain numbers or arrays; xarray objects pass through unchanged
        a, b = np.asarray(a, float), np.asarray(b, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def ndvi(nir, red):
    """Normalised Difference Vegetation Index (Rouse et al. 1974). -1 to 1; dense vegetation about 0.6-0.9."""
    return nd(nir, red)


def ndwi(green, nir):
    """Normalised Difference Water Index (McFeeters 1996): open water above 0."""
    return nd(green, nir)


def mndwi(green, swir1):
    """Modified NDWI (Xu 2006): separates water from built-up land better than NDWI."""
    return nd(green, swir1)


def ndbi(swir1, nir):
    """Normalised Difference Built-up Index (Zha et al. 2003)."""
    return nd(swir1, nir)


def ndsi(green, swir1):
    """Normalised Difference Snow Index (Hall et al. 1995); snow commonly above 0.4."""
    return nd(green, swir1)


def nbr(nir, swir2):
    """Normalised Burn Ratio (Key and Benson 2006); dNBR = pre - post measures burn severity."""
    return nd(nir, swir2)


def ndmi(nir, swir1):
    """Normalised Difference Moisture Index (Gao 1996, as NDWI of vegetation water)."""
    return nd(nir, swir1)


def evi(nir, red, blue, G=2.5, C1=6.0, C2=7.5, L=1.0):
    """Enhanced Vegetation Index (Huete et al. 2002): G (nir - red) / (nir + C1 red - C2 blue + L). Needs 0-1 reflectance."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return G * (nir - red) / (nir + C1 * red - C2 * blue + L)


def savi(nir, red, L=0.5):
    """Soil-Adjusted Vegetation Index (Huete 1988): (1 + L)(nir - red) / (nir + red + L). Needs 0-1 reflectance."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return (1 + L) * (nir - red) / (nir + red + L)


# name: (function, roles in argument order)
INDEX = {"ndvi": (ndvi, ("nir", "red")), "ndwi": (ndwi, ("green", "nir")), "mndwi": (mndwi, ("green", "swir1")),
         "ndbi": (ndbi, ("swir1", "nir")), "ndsi": (ndsi, ("green", "swir1")), "nbr": (nbr, ("nir", "swir2")),
         "ndmi": (ndmi, ("nir", "swir1")), "evi": (evi, ("nir", "red", "blue")), "savi": (savi, ("nir", "red"))}


def compute(name, bands, sensor="sentinel2"):
    """Compute an index by name from a mapping of band name to array (e.g. an xarray Dataset), using BANDS[sensor]."""
    fn, roles = INDEX[name]
    return fn(*(bands[BANDS[sensor][r]] for r in roles))


def add_ee(image, names, sensor="sentinel2"):
    """Add indices to an Earth Engine image as bands named in capitals (NDVI, ...). The image must hold 0-1 reflectance.

    Normalised differences use normalizedDifference; EVI and SAVI use expression() with the same constants as above."""
    b = BANDS[sensor]
    out = image
    for n in names:
        _, roles = INDEX[n]
        if n == "evi":
            band = image.expression("2.5*(N-R)/(N+6*R-7.5*B+1)", {"N": image.select(b["nir"]), "R": image.select(b["red"]), "B": image.select(b["blue"])})
        elif n == "savi":
            band = image.expression("1.5*(N-R)/(N+R+0.5)", {"N": image.select(b["nir"]), "R": image.select(b["red"])})
        else:
            band = image.normalizedDifference([b[roles[0]], b[roles[1]]])
        out = out.addBands(band.rename(n.upper()))
    return out
