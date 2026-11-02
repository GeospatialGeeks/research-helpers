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


def story_map(stem, projection, draw, *, title, subtitle, key=(), legend=(), method="", source="", author="", map_share=0.62, page=(1080, 1920), dpi=200, key_wrap=31, note_wrap=66):
    """A map that explains itself on one screen, for a story or a slide: title, map, two-column key, legend, one short note.

    draw(ax, fig) adds the map content. key is [(number, name, few words)]. legend is [(colour, label)]. Keep the text short:
    the page raises an error if it overflows. Use page=(1080, 1350) for a portrait post.
    """
    w, h = page[0] / dpi, page[1] / dpi
    fig = plt.figure(figsize=(w, h), facecolor="white")
    margin = 0.03
    line = lambda size: size * 1.25 / 72 / h
    y = 0.985
    fig.text(margin, y, title, fontsize=17, fontweight="bold", va="top", color=INK)
    y -= line(17) + 0.004
    fig.text(margin, y, subtitle, fontsize=9.5, va="top", color="#333333", linespacing=1.2)
    y -= line(9.5) * (subtitle.count("\n") + 1) + 0.008
    ax = fig.add_axes([0, y - map_share, 1, map_share], projection=projection)
    draw(ax, fig)
    y -= map_share + 0.012
    if legend:
        x = margin
        for colour, label in legend:
            fig.patches.append(plt.Rectangle((x, y - 0.012), 0.04, 0.012, transform=fig.transFigure, facecolor=colour, edgecolor="#555555", linewidth=0.3))
            fig.text(x + 0.048, y - 0.006, label, fontsize=9, va="center", color=INK)
            x += 0.07 + 0.0148 * len(label)
        y -= 0.024
    rows = (len(key) + 1) // 2
    heights = []
    for r in range(rows):
        cells = key[2 * r:2 * r + 2]
        n_lines = 1
        for c, (number, name, what) in enumerate(cells):
            x = margin + c * 0.485
            lines = textwrap.wrap(f"{name}: {what}", key_wrap)
            n_lines = max(n_lines, len(lines))
            fig.text(x + 0.016, y - 0.001, str(number), fontsize=9, fontweight="bold", ha="center", va="top", bbox=dict(boxstyle="circle,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5))
            fig.text(x + 0.05, y, "\n".join(lines), fontsize=9, va="top", color=INK, linespacing=1.15)
        y -= line(9) * n_lines + 0.009
    y -= 0.002
    note = " ".join(s for s in (method, source) if s)
    if note:
        lines = textwrap.wrap(note, note_wrap)
        fig.text(margin, y, "\n".join(lines), fontsize=7.8, va="top", color="#444444", linespacing=1.15)
        y -= line(7.8) * len(lines)
    if y < 0.018:
        raise ValueError(f"the page overflows by {0.018 - y:.3f}: shorten the text or the map")
    if author:
        fig.text(1 - margin, 0.008, author, fontsize=7, ha="right", color="#666666")
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), dpi=dpi, bbox_inches=None, facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), dpi=dpi, bbox_inches=None, facecolor="white", metadata={"Title": title, "CreationDate": None})
    fig.savefig(stem.with_suffix(".svg"), dpi=dpi, bbox_inches=None, facecolor="white", metadata={"Title": title, "Date": None})
    _story_pptx(fig, stem, page, dpi)
    plt.close(fig)
    return stem


def _story_pptx(fig, stem, page, dpi):
    """An editable slide: the map and legend swatches as one picture, and every piece of page text as its own text box."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Emu, Pt
    EMU = 914400 / dpi
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(int(page[0] * EMU)), Emu(int(page[1] * EMU))
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    texts = list(fig.texts)
    for x in texts:
        x.set_visible(False)
    picture = stem.parent / f"{stem.name}_base.png"
    fig.savefig(picture, dpi=dpi, bbox_inches=None, facecolor="white")
    for x in texts:
        x.set_visible(True)
    slide.shapes.add_picture(str(picture), 0, 0, prs.slide_width, prs.slide_height)
    renderer = fig.canvas.get_renderer()
    scale = dpi / fig.dpi
    for x in texts:
        box = x.get_window_extent(renderer)
        left, top = box.x0 * scale * EMU, (fig.bbox.height - box.y1) * scale * EMU
        width = max(box.width * scale * EMU * 1.12, 300000)
        tb = slide.shapes.add_textbox(Emu(int(left)), Emu(int(top)), Emu(int(width)), Emu(int(box.height * scale * EMU)))
        f = tb.text_frame
        f.margin_left = f.margin_right = f.margin_top = f.margin_bottom = 0
        f.word_wrap = False
        for i, s in enumerate(x.get_text().split("\n")):
            para = f.paragraphs[0] if i == 0 else f.add_paragraph()
            run = para.add_run()
            run.text = s
            run.font.size = Pt(x.get_fontsize())
            run.font.bold = x.get_fontweight() == "bold"
            run.font.name = "Arial"
            r, g, b = [int(c * 255) for c in mpl.colors.to_rgb(x.get_color())]
            run.font.color.rgb = RGBColor(r, g, b)
    prs.save(stem.with_suffix(".pptx"))
