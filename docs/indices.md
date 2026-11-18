# Spectral indices (`research_helpers.indices`)

Spectral indices from surface reflectance, for NumPy arrays, xarray objects or Earth Engine images.

    from research_helpers import indices
    ndvi = indices.ndvi(nir, red)                         # arrays or DataArrays of reflectance (0-1)
    img = indices.add_ee(image, ["ndvi", "ndwi"], sensor="landsat_oli")   # Earth Engine: adds bands named NDVI, NDWI

Reflectance must be scaled to 0-1 first (Landsat Collection 2 Level 2: x 0.0000275 - 0.2; Sentinel-2 L2A: / 10000,
less 0.1 for products from January 2022 that are not harmonised). Indices that use constants (EVI, SAVI) are wrong on
unscaled digital numbers; normalised differences are not, but scale anyway so every index is on one footing.

Each index lists its source. The band each one needs, by sensor, is in BANDS.

## Functions and classes

**`add_ee(image, names, sensor='sentinel2')`**

Add indices to an Earth Engine image as bands named in capitals (NDVI, ...). The image must hold 0-1 reflectance.

Normalised differences use normalizedDifference; EVI and SAVI use expression() with the same constants as above.

**`compute(name, bands, sensor='sentinel2')`**

Compute an index by name from a mapping of band name to array (e.g. an xarray Dataset), using BANDS[sensor].

**`evi(nir, red, blue, G=2.5, C1=6.0, C2=7.5, L=1.0)`**

Enhanced Vegetation Index (Huete et al. 2002): G (nir - red) / (nir + C1 red - C2 blue + L). Needs 0-1 reflectance.

**`mndwi(green, swir1)`**

Modified NDWI (Xu 2006): separates water from built-up land better than NDWI.

**`nbr(nir, swir2)`**

Normalised Burn Ratio (Key and Benson 2006); dNBR = pre - post measures burn severity.

**`nd(a, b)`**

Normalised difference (a - b) / (a + b); NaN where a + b is zero.

**`ndbi(swir1, nir)`**

Normalised Difference Built-up Index (Zha et al. 2003).

**`ndmi(nir, swir1)`**

Normalised Difference Moisture Index (Gao 1996, as NDWI of vegetation water).

**`ndsi(green, swir1)`**

Normalised Difference Snow Index (Hall et al. 1995); snow commonly above 0.4.

**`ndvi(nir, red)`**

Normalised Difference Vegetation Index (Rouse et al. 1974). -1 to 1; dense vegetation about 0.6-0.9.

**`ndwi(green, nir)`**

Normalised Difference Water Index (McFeeters 1996): open water above 0.

**`savi(nir, red, L=0.5)`**

Soil-Adjusted Vegetation Index (Huete 1988): (1 + L)(nir - red) / (nir + red + L). Needs 0-1 reflectance.
