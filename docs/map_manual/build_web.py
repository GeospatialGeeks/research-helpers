"""Web edition of the map manual, through the shared converter. Needs a finished PDF build first."""
from pathlib import Path

from research_helpers import tex_web as T

HERE = Path(__file__).resolve().parent
SITE = Path.home() / "dev/AhmadAmmar.github.io"
TEX = HERE / "tex"
SNIPPET = r"\newcommand{\snippetcaption}[1]{\textbf{From the code:} \texttt{#1}}"
PROJECT = T.Project(
    root=TEX, aux=TEX / "main.aux", url="/teaching/maps/", out=SITE / "src/maps", figures=SITE / "teaching/maps/fig",
    chapters=[T.Chapter(s, TEX / f"ch_{f}.tex") for s, f in (("anatomy", "anatomy"), ("tools", "stack"), ("projections", "projection"), ("colour", "colour"), ("components", "components"), ("workflow", "workflow"))],
    preamble=[r"\documentclass[11pt,a4paper]{article}", r"\usepackage[T1]{fontenc}", r"\usepackage{lmodern,caption,amsmath,graphicx,booktabs,xcolor,listings,float,tabularx}", r"\usepackage[margin=24mm]{geometry}", r"\graphicspath{{../figures/}}", SNIPPET],
    macros=SNIPPET + "\n", description="{label}: Making maps that can be repeated and published.", search=[TEX], inline_generated=("snip_", "areas"),
    index_head=["---", "slug: index", "title: Making maps that can be repeated and published", "description: A programming manual for reproducible maps with Python, Matplotlib and Cartopy.", "---", "", "A programming manual for maps that can be repeated and published, using Python, Matplotlib, Cartopy and research-helpers. You can also read the [whole manual on one page](full/) or download the [PDF](/files/Reproducible_maps_Ahmad_Ammar.pdf).", ""],
)
if __name__ == "__main__":
    print(T.build_figures(PROJECT))
    T.build_pages(PROJECT)
