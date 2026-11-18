# Rasters, terrain, SAR and lidar (`research_helpers.rasters`)

Rasters: reading and writing GeoTIFFs, terrain, SAR backscatter, lidar heights and zonal statistics.

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

## Functions and classes

**`glcm_features(band, levels=32, distance=1, props=('contrast', 'homogeneity', 'energy', 'correlation'))`**

Haralick texture of a whole image or window: band is rescaled to `levels` grey levels between its 1st and 99th
percentiles, co-occurrence counted at `distance` in four directions and averaged. Needs scikit-image.

**`hillshade(dem, cell, azimuth=315, altitude=45)`**

Shaded relief 0-1 for a light source at azimuth (degrees from north) and altitude (degrees above horizon).

**`lee_filter(power, size=7, looks=4.4)`**

Lee speckle filter on linear power. looks is the equivalent number of looks (about 4.4 for Sentinel-1 IW GRD).

Each pixel moves towards the local mean by a weight that is small in flat areas (speckle) and near one at edges.

**`local_relief(dem, size)`**

Highest minus lowest elevation in a size x size window around each cell (kkh-hazard used 67 cells, about 2 km
at 30 m). No-data cells stay NaN and do not count.

**`mean_db(stack_db, axis=0)`**

Average a stack of dB images in linear power and return dB. Averaging decibels directly gives the geometric
mean, which understates bright targets (by about 2.5 dB for fully developed speckle).

**`ndsm(dsm, dtm, floor=0.0)`**

Normalised surface model: height above ground = DSM - DTM, with values below `floor` set to it.

**`read(path, band=1)`**

One band as float64 with no-data set to NaN, and the rasterio profile (CRS, transform, size) for writing back.

**`slope_aspect(dem, cell, cell_y=None)`**

Slope (degrees) and aspect (degrees clockwise from north, the way the slope faces) by Horn's 3 x 3 method.

dem in metres on a projected grid with square cells of size cell (m); north is up (row 0 is the northern edge).
Edges are NaN. Agrees with GDAL's gdaldem slope and aspect to within 0.001 degrees (checked on a test surface).

**`stretch(a, low=2, high=98)`**

Scale to 0-1 between two percentiles, for display only (never for analysis).

**`to_db(linear)`**

Backscatter in decibels from linear power: 10 log10(x). Zero and negative values give NaN.

**`to_linear(db)`**

Linear power from decibels: 10^(dB/10).

**`write(path, array, profile, nodata=-9999.0, keep_old=True)`**

Write a float32 GeoTIFF, compressed and tiled, NaN written as nodata. Earlier versions are archived with
safeio.keep() unless keep_old=False.

**`zonal(values, labels, min_valid=0.0, stats=('mean', 'median', 'count'))`**

Statistics of `values` within each integer label (0 = no zone), e.g. building heights within footprints.

Returns a dict of arrays indexed by label, and the share of each zone's cells that were valid. Zones whose valid
share is below min_valid get NaN (the PhD used 0.5 for lidar heights per footprint).
