"""House style for maps and figures, on top of Cartopy, matplotlib-scalebar and Crameri's scientific colour maps.

Needs the optional extra: pip install research-helpers[carto]

    from research_helpers import carto
    carto.use_style()
    fig, ax = carto.map_axes(carto.albers(85, 25, 45), [60, 105, 22, 46], width="double")
    carto.scale_bar(ax); carto.save(fig, "figures/map")
"""
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.pyplot as plt
from cmcrameri import cm
from matplotlib_scalebar.scalebar import ScaleBar

# widths most journals accept, in inches
WIDTH = {"single": 3.5, "onehalf": 5.5, "double": 7.2}
INK = "#222222"
# Okabe-Ito, safe for the common colour-vision deficiencies
QUALITATIVE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
SEQUENTIAL = cm.batlow
DIVERGING = cm.vik
ELEVATION = cm.oleron
MUTED_LAND, MUTED_WATER, GRID = "#f4f2ec", "#dfe9ef", "#b8b8b8"


def use_style():
    """Set fonts, weights and export options once, so every figure in a project matches."""
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Source Sans 3", "Source Sans Pro", "Arial", "DejaVu Sans"], "font.size": 8,
        "axes.titlesize": 9, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "axes.edgecolor": INK, "axes.labelcolor": INK,
        "xtick.color": INK, "ytick.color": INK, "xtick.labelsize": 7, "ytick.labelsize": 7, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "legend.frameon": False, "legend.fontsize": 7, "lines.linewidth": 1.1, "figure.dpi": 150, "savefig.dpi": 400, "savefig.bbox": "tight",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "axes.prop_cycle": mpl.cycler(color=QUALITATIVE),
    })


def size(width="double", ratio=0.62):
    w = WIDTH.get(width, width)
    return w, w * ratio


def albers(central_lon, parallel_1, parallel_2, central_lat=None):
    """Equal-area conic, the usual choice for mid-latitude regions wider than they are tall."""
    lat = (parallel_1 + parallel_2) / 2 if central_lat is None else central_lat
    return ccrs.AlbersEqualArea(central_longitude=central_lon, central_latitude=lat, standard_parallels=(parallel_1, parallel_2))


def map_axes(projection, extent=None, width="double", ratio=0.62, ax=None, grid=True, land=True, step=(10, 10)):
    """A map with quiet land, sea and graticule. Extent is lon0, lon1, lat0, lat1 in degrees."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=size(width, ratio), subplot_kw={"projection": projection})
    if extent:
        ax.set_extent(extent, ccrs.PlateCarree())
    if land:
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor=MUTED_LAND, edgecolor="none", zorder=0)
        ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor=MUTED_WATER, edgecolor="none", zorder=0)
    if grid:
        g = ax.gridlines(draw_labels=True, x_inline=False, y_inline=False, linewidth=0.3, color=GRID, xlocs=mpl.ticker.MultipleLocator(step[0]), ylocs=mpl.ticker.MultipleLocator(step[1]))
        g.top_labels = g.right_labels = False
        g.xlabel_style = g.ylabel_style = {"size": 6.5, "color": INK}
    ax.spines["geo"].set_linewidth(0.5)
    return (fig, ax) if fig else ax


def scale_bar(ax, location="lower left"):
    """Scale bar in metres of the map's projection. It is true along the standard parallels only; say so in the caption."""
    bar = ScaleBar(1, "m", location=location, frameon=False, font_properties={"size": 6.5}, length_fraction=0.18, width_fraction=0.008, color=INK, scale_loc="top")
    ax.add_artist(bar)
    return bar


def panel_labels(axes, x=-0.02, y=1.03):
    for i, ax in enumerate(axes):
        ax.text(x, y, f"({chr(97 + i)})", transform=ax.transAxes, fontweight="bold", fontsize=9, va="bottom", ha="right")


def save(fig, stem, formats=("pdf", "png", "svg"), meta=None):
    """Save vector and raster copies, without a timestamp so that a rebuild of the same figure is byte-stable where possible."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    for f in formats:
        md = {"Title": stem.name, **(meta or {})}
        if f == "pdf":
            md["CreationDate"] = None
        elif f == "svg":
            md["Date"] = None
        elif f == "png":
            md = {"Title": stem.name}
        fig.savefig(stem.with_suffix(f".{f}"), metadata=md)
    return stem
