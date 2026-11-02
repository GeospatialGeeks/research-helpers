"""Every figure in the map manual, drawn with research_helpers.carto from open boundary files in the shared-geodata repository.

    python make_figures.py
"""
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from cmcrameri import cm

from research_helpers import carto

R = Path(__file__).resolve().parent.parent
F = R / "figures"
GEO = Path.home() / "dev/shared-geodata/data"
carto.use_style()
regions = gpd.read_file(GEO / "third_pole/third_pole_regions_v2.geojson")
ranges = regions[regions.level == "range"]
divisions = regions[regions.level == "division"]
PROJ = carto.albers(85, 25, 45)
EXTENT = [60, 108, 22, 47]
SRC = ["GMBA Mountain Inventory v2", "Natural Earth"]


def anatomy():
    fig, ax = carto.map_axes(PROJ, EXTENT, width="double", ratio=0.62)
    cats = sorted(ranges.unit)
    for i, u in enumerate(cats):
        ax.add_geometries(ranges[ranges.unit == u].geometry, ccrs.PlateCarree(), facecolor=carto.QUALITATIVE[i], edgecolor="white", linewidth=0.2, zorder=2)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=carto.QUALITATIVE[i]) for i in range(len(cats))], cats, loc="lower left", title="Mountain range", title_fontsize=7, fontsize=6, frameon=True)
    ax.set_title("Mountain ranges of the Third Pole")
    carto.scale_bar(ax, "lower right")
    carto.locator(fig, [0.74, 0.60, 0.17, 0.26], [-20, 150, 0, 75], (60, 108, 22, 47))
    carto.credit(fig, "Sources: GMBA Mountain Inventory v2; Natural Earth. " + carto.BOUNDARY_NOTE)
    carto.finish_map(fig, F / "map_anatomy", title="Mountain ranges of the Third Pole", sources=SRC, crs="Albers equal-area, parallels 25N and 45N", boundary_note=True)
    plt.close(fig)


def projections():
    fig, ax = plt.subplots(1, 3, figsize=carto.size("double", 0.34), subplot_kw={"projection": PROJ})
    for a, (name, crs) in zip(ax, (("Plate carree", ccrs.PlateCarree()), ("Web Mercator", ccrs.Mercator.GOOGLE), ("Albers equal-area", PROJ))):
        a.remove()
    axes = [fig.add_subplot(1, 3, i + 1, projection=c) for i, c in enumerate((ccrs.PlateCarree(), ccrs.Mercator.GOOGLE, PROJ))]
    for a, t in zip(axes, ("Plate carree", "Web Mercator", "Albers equal-area")):
        a.set_extent(EXTENT, ccrs.PlateCarree())
        a.coastlines("50m", linewidth=0.3)
        a.add_geometries(ranges.geometry, ccrs.PlateCarree(), facecolor=carto.QUALITATIVE[0], edgecolor="none", alpha=0.8)
        a.gridlines(linewidth=0.3, color=carto.GRID)
        a.set_title(t)
    carto.panel_labels(axes)
    carto.finish_map(fig, F / "fig_projections", title="One region in three projections", sources=SRC, crs="As labelled", scale_bar="A comparison of shape only.")
    plt.close(fig)
    rows = []
    for name, crs in (("Geographic degrees treated as flat, at the equator's scale", None), ("Web Mercator", "EPSG:3857"), ("Albers equal-area (ours)", PROJ.proj4_init), ("Equal Earth", "ESRI:54035")):
        for lat, unit in ((27.5, "Himalaya"),):
            pass
        g = ranges.set_index("unit").geometry
        if crs is None:
            k = g.area * 111.32 ** 2
        else:
            k = g.to_crs(crs).area / 1e6
        rows.append((name, float(k["Karakoram"]), float(k["Tian Shan"])))
    base = rows[-1]
    (R / "tex/generated").mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{n} & {a:,.0f} & {100 * (a / base[1] - 1):+.0f}\\% & {b:,.0f} & {100 * (b / base[2] - 1):+.0f}\\% \\\\" for n, a, b in rows).replace(",", "{,}")
    (R / "tex/generated/areas.tex").write_text("\\begin{tabular}{p{5.2cm}rrrr}\n\\toprule\nHow area is computed & Karakoram (km$^2$) & Error & Tian Shan (km$^2$) & Error \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf8")


def colours():
    x = np.linspace(0, 1, 256)[None, :]
    maps = [("batlow: sequential, ordered values", cm.batlow), ("vik: diverging, around a meaningful zero", cm.vik), ("oleron: terrain, with land and sea", cm.oleron), ("jet: avoid", plt.get_cmap("jet"))]
    fig, ax = plt.subplots(len(maps), 2, figsize=carto.size("double", 0.3), gridspec_kw={"width_ratios": [4, 1]})
    for row, (name, c) in zip(ax, maps):
        row[0].imshow(x, cmap=c, aspect="auto")
        row[0].set_title(name, fontsize=7)
        l = plt.cm.ScalarMappable(cmap=c).to_rgba(x)[0, :, :3] @ np.array([0.2126, 0.7152, 0.0722])
        row[1].plot(l, color="#222222", lw=0.9)
        row[1].set_ylim(0, 1)
        row[1].set_xticks([])
        row[0].set_axis_off()
        row[1].set_yticks([0, 1])
    fig.tight_layout()
    carto.save(fig, F / "fig_colours")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=carto.size("double", 0.11))
    for i, c in enumerate(carto.QUALITATIVE):
        ax.add_patch(plt.Rectangle((i, 0), 1, 1, color=c))
        ax.text(i + 0.5, -0.25, c, ha="center", fontsize=6)
    ax.set_xlim(0, 8)
    ax.set_ylim(-0.5, 1)
    ax.set_axis_off()
    carto.save(fig, F / "fig_palette")
    plt.close(fig)


def before_after():
    fig = plt.figure(figsize=carto.size("double", 0.42))
    a = fig.add_subplot(1, 2, 1, projection=ccrs.PlateCarree())
    a.set_extent(EXTENT, ccrs.PlateCarree())
    a.stock_img() if False else None
    a.add_geometries(divisions.geometry, ccrs.PlateCarree(), facecolor="none", edgecolor="red", linewidth=1.0)
    a.gridlines(draw_labels=True, linewidth=1.0, color="black")
    a.set_title("Defaults")
    b = fig.add_subplot(1, 2, 2, projection=PROJ)
    carto.map_axes(PROJ, EXTENT, ax=b)
    keys = sorted(divisions.parent.unique())
    for i, k in enumerate(keys):
        b.add_geometries(divisions[divisions.parent == k].geometry, ccrs.PlateCarree(), facecolor=carto.QUALITATIVE[i], edgecolor="white", linewidth=0.15, zorder=2)
    carto.scale_bar(b, "lower right")
    b.set_title("With the house style")
    carto.panel_labels([a, b])
    carto.finish_map(fig, F / "fig_before_after", title="Defaults and house style", sources=SRC, crs="Plate carree, and Albers equal-area", scale_bar="Panel (a) is an example of what to avoid.")
    plt.close(fig)


anatomy(); projections(); colours(); before_after()
print(sorted(p.name for p in F.glob("*.png")))
