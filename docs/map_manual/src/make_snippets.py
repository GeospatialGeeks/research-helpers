"""Code excerpts for the map manual, taken from the real library."""
from pathlib import Path

import research_helpers.carto as c
from research_helpers.snippets import function_listing

R = Path(__file__).resolve().parent.parent
G = R / "tex/generated"
for name in ("use_style", "albers", "map_axes", "scale_bar", "mark", "outlined", "locator", "credit", "save", "finish_map", "panel_labels", "size"):
    function_listing(c.__file__, name, G / f"snip_{name}.tex", f"research_helpers/carto.py, {name}()")
