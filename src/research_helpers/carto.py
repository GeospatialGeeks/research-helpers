"""House style for maps and figures, on top of Cartopy, matplotlib-scalebar and Crameri's scientific colour maps.

Needs the optional extra: pip install research-helpers[carto]

    from research_helpers import carto
    carto.use_style()
    fig, ax = carto.map_axes(carto.albers(85, 25, 45), [60, 105, 22, 46], width="double")
    carto.scale_bar(ax); carto.save(fig, "figures/map")
"""
import json
import textwrap
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.patheffects as pe
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
BOUNDARY_NOTE = "Boundaries imply no position on any territorial claim."
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
    bar = ScaleBar(1, "m", location=location, frameon=True, box_color="white", box_alpha=0.8, font_properties={"size": 6.5}, length_fraction=0.18, width_fraction=0.008, color=INK, scale_loc="top")
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


def mark(ax, points, transform=None, size=7):
    """Numbered markers with a halo, readable over any image. points is a list of (number, x, y); a caption or key explains them."""
    transform = transform or ccrs.PlateCarree()
    for n, x, y in points:
        ax.text(x, y, str(n), transform=transform, ha="center", va="center", fontsize=size, fontweight="bold", color="black", zorder=20,
                bbox=dict(boxstyle="circle,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.5))


def outlined(ax, x, y, text, transform=None, size=7, color="white"):
    """A place label with an outline, for use over imagery."""
    return ax.text(x, y, text, transform=transform or ccrs.PlateCarree(), fontsize=size, color=color, zorder=19, path_effects=[pe.withStroke(linewidth=1.8, foreground="black")])


def locator(fig, position, extent, box, projection=None):
    """Small overview map. position is [left, bottom, width, height] in figure units; box is the lon0, lon1, lat0, lat1 of the main map."""
    a = fig.add_axes(position, projection=projection or ccrs.PlateCarree())
    a.set_extent(extent, ccrs.PlateCarree())
    a.add_feature(cfeature.LAND.with_scale("50m"), facecolor=MUTED_LAND, edgecolor="#666666", linewidth=0.3)
    a.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor=MUTED_WATER)
    a.add_feature(cfeature.BORDERS.with_scale("50m"), edgecolor="#888888", linewidth=0.3)
    x0, x1, y0, y1 = box
    a.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color="#D55E00", linewidth=0.9, transform=ccrs.PlateCarree())
    return a


def credit(fig, text, y=0.005):
    fig.text(0.995, y, text, ha="right", va="bottom", fontsize=5.5, color="#444444")


def finish_map(fig, stem, *, title, sources, crs, scale_bar=True, boundary_note=False, status="final", note="", formats=("pdf", "png", "svg")):
    """The one exit for a map: it stops if basic elements are missing, and saves a record beside the map.

    A map must name its sources and projection and either carry a scale bar or say why not. The record makes it findable and repeatable.
    """
    if not sources:
        raise ValueError("a map must name its sources")
    if not crs:
        raise ValueError("a map must state its projection")
    if scale_bar is not True and not isinstance(scale_bar, str):
        raise ValueError("a map needs a scale bar, or a sentence saying why not")
    s = save(fig, stem, formats, {"Title": title})
    record = dict(title=title, sources=list(sources), crs=crs, scale_bar=scale_bar, boundary_note=BOUNDARY_NOTE if boundary_note else "", status=status, note=note, files=[s.with_suffix(f".{f}").name for f in formats])
    s.with_suffix(".map.json").write_text(json.dumps(record, indent=1), encoding="utf8")
    return s


def story_map(stem, projection, draw, *, title, subtitle, key=(), legend=(), method="", source="", author="", map_share=None, map_aspect=1.0, page=(1080, 1920), dpi=200):
    """A map that explains itself on one page, for social media or a slide: title, map, numbered key, legend, method and source.

    draw(ax, fig) adds the map content. key is [(number, name, what it shows)]. legend is [(colour, label)]. map_aspect is height over width.
    The sizes suit a 1080 by 1920 story; pass page=(1080, 1350) for a portrait post.
    """
    w, h = page[0] / dpi, page[1] / dpi
    fig = plt.figure(figsize=(w, h), facecolor="white")
    margin = 0.045
    fig.text(margin, 0.972, title, fontsize=15, fontweight="bold", va="top", color=INK, wrap=True)
    n_title = title.count("\n") + 1
    top = 0.972 - 0.031 * n_title
    fig.text(margin, top, subtitle, fontsize=8.2, va="top", color="#444444", linespacing=1.25)
    top -= 0.0175 * (subtitle.count("\n") + 1) + 0.012
    map_h = (map_share if map_share else min((1 - 2 * margin) * w * map_aspect / h, 0.56))
    ax = fig.add_axes([margin + 0.05, top - map_h, 1 - 2 * margin - 0.05, map_h], projection=projection)
    draw(ax, fig)
    y = top - map_h - 0.03
    line = lambda size: size * 1.27 / 72 / h
    if legend:
        x = margin
        for colour, label in legend:
            fig.patches.append(plt.Rectangle((x, y - 0.012), 0.036, 0.014, transform=fig.transFigure, facecolor=colour, edgecolor="#555555", linewidth=0.3))
            fig.text(x + 0.045, y - 0.005, label, fontsize=8, va="center", color=INK)
            x += 0.06 + 0.0122 * len(label)
        y -= 0.033
    for number, name, what in key:
        fig.text(margin + 0.016, y - 0.002, str(number), fontsize=8.5, fontweight="bold", ha="center", va="top", color="black", bbox=dict(boxstyle="circle,pad=0.22", facecolor="white", edgecolor="black", linewidth=0.5))
        lines = textwrap.wrap(f"{name}: {what}", 62)
        fig.text(margin + 0.052, y, "\n".join(lines), fontsize=8.8, va="top", color=INK, linespacing=1.2)
        y -= line(8.8) * len(lines) + 0.011
    y -= 0.006
    for label, text in (("How it was made", method), ("Sources", source)):
        if text:
            fig.text(margin, y, label, fontsize=8.2, fontweight="bold", va="top", color=INK)
            y -= line(8.2) + 0.002
            lines = textwrap.wrap(text, 72)
            fig.text(margin, y, "\n".join(lines), fontsize=8, va="top", color="#333333", linespacing=1.2)
            y -= line(8) * len(lines) + 0.012
    if y < 0.012:
        raise ValueError(f"the page overflows by {0.012 - y:.3f}: shorten the text or the map")
    if author:
        fig.text(1 - margin, 0.012, author, fontsize=6.5, ha="right", color="#666666")
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), dpi=dpi, bbox_inches=None, facecolor="white")
    plt.close(fig)
    return stem
