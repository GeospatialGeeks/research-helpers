"""Inventory of the code across many projects: every function, whether it is documented, and where the same job is done twice.

    python -m research_helpers.inventory ROOT [ROOT ...] --out inventory/

Writes three files to the output folder:

    functions.csv    one row per Python function or JavaScript function: project, file, name, lines, docstring yes/no, topic
    duplicates.csv   functions whose bodies are identical or whose names recur across projects (candidates for one shared copy)
    summary.md       counts per project and per topic, and the share of functions with a docstring

Topics are found from names and bodies with simple keyword rules (TOPICS below), so they are a guide for sorting, not a
classification. Folders that hold copies, environments or build output (SKIP) are left out.
"""
import argparse
import ast
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

# Folders never scanned: environments, packages, builds, archives and version control.
SKIP = {".git", "node_modules", "site-packages", ".venv", "venv", "env", "__pycache__", "_archive", "archive",
        "build", "dist", "_site", ".ipynb_checkpoints", "vendor", "lib", ".mypy_cache", ".pytest_cache", "_build"}

# Topic: keywords searched in a function's name and body (lower case). The first matching topic wins, so the
# more specific topics come first.
TOPICS = [
    ("earth-engine", r"\bee\.|earthengine|ee_|getinfo\(|export\.image"),
    ("lidar", r"lidar|laspy|\.laz\b|\.las\b|pdal|point ?cloud|canopy height"),
    ("sar", r"\bsar\b|sentinel-?1|s1_grd|backscatter|\bvv\b|\bvh\b|insar|sigma0|gamma0"),
    ("gedi", r"gedi|\brh\d+|agbd"),
    ("spectral-index", r"ndvi|ndwi|ndbi|ndsi|evi\b|savi|nbr\b|spectral index|reflectance"),
    ("snow-ice", r"snow|glacier|ndsi|cryo"),
    ("climate", r"era5|cmip|precip|temperature|anomal|trend|monsoon|climatolog|hdd\b|degree.day"),
    ("air-quality", r"pm2\.?5|aerosol|aod\b|no2|smog|air quality|tropomi"),
    ("hydrology", r"grace|groundwater|runoff|discharge|aquifer|tws\b|modflow"),
    ("buildings-energy", r"epc|rdsap|sap\b|u_value|u-value|heat loss|footprint|building|dwelling|retrofit"),
    ("raster", r"rasterio|gdal|xarray|rioxarray|reproject|resampl|\.tif|geotiff|zonal"),
    ("vector-gis", r"geopandas|shapely|\.to_crs|crs\b|polygon|buffer\(|sjoin|overlay\("),
    ("mapping", r"cartopy|basemap|choropleth|colorbar|legend|leaflet|maplibre|folium|scalebar|north arrow"),
    ("plotting", r"matplotlib|plt\.|savefig|seaborn|plotly"),
    ("statistics-ml", r"sklearn|regress|spearman|bootstrap|cross.?val|xgboost|random ?forest|auc\b|statsmodels"),
    ("data-access", r"requests\.|urllib|stac|earthaccess|cdsapi|api_key|download|netrc|token"),
    ("documents", r"latex|bibtex|\.tex\b|pandoc|docx|pdf|citation|zotero"),
    ("web", r"html|javascript|css|github pages|jekyll"),
    ("files-io", r"open\(|read_csv|to_csv|json\.|pathlib|shutil"),
]
TOPIC_RE = [(t, re.compile(p)) for t, p in TOPICS]


def topic(text):
    """Return the first topic whose keywords appear in text, or 'general'."""
    low = text.lower()
    for t, rx in TOPIC_RE:
        if rx.search(low):
            return t
    return "general"


def project_of(path, roots):
    """Name a file's project: the first folder below the root it was found under."""
    for r in roots:
        try:
            rel = path.relative_to(r)
        except ValueError:
            continue
        return rel.parts[0] if len(rel.parts) > 1 else r.name
    return "?"


def files(roots, exts):
    """Yield source files under the roots, skipping the folders in SKIP."""
    for r in roots:
        for p in r.rglob("*"):
            if p.suffix in exts and p.is_file() and not (SKIP & set(x.lower() for x in p.parts)):
                yield r, p


def python_functions(path):
    """Yield (name, first line, last line, has docstring, normalised body) for every function in a Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.dump(ast.Module(body=[b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))], type_ignores=[]))
            yield node.name, node.lineno, getattr(node, "end_lineno", node.lineno), ast.get_docstring(node) is not None, body


JS_FUNC = re.compile(r"(?:function\s+([A-Za-z_$][\w$]*)\s*\(|(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:function\b|\([^)]*\)\s*=>))")


def js_functions(path):
    """Yield the same tuple as python_functions for named JavaScript functions (Earth Engine scripts, web pages).

    A function counts as documented when a // or /* comment ends on the line just above it."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        m = JS_FUNC.search(line)
        if m:
            prev = lines[i - 1].strip() if i else ""
            documented = prev.startswith("//") or prev.endswith("*/")
            body = "\n".join(lines[i:i + 40])
            yield m.group(1) or m.group(2), i + 1, i + 1, documented, re.sub(r"\s+", " ", body)


def scan(roots):
    """Return one dictionary per function found under the roots."""
    rows = []
    for root, p in files(roots, {".py", ".js"}):
        gen = python_functions(p) if p.suffix == ".py" else js_functions(p)
        text = None
        for name, a, b, doc, body in gen:
            if text is None:
                text = p.read_text(encoding="utf-8", errors="replace")
            rows.append({"project": project_of(p, roots), "file": str(p), "language": p.suffix[1:], "name": name,
                         "line": a, "lines": b - a + 1, "docstring": doc, "topic": topic(name + " " + body),
                         "hash": hashlib.sha1(body.encode()).hexdigest()[:12]})
    return rows


def duplicates(rows):
    """Functions with identical bodies in more than one file, and public names defined in three or more projects."""
    out = []
    by_hash = defaultdict(list)
    for r in rows:
        if r["lines"] >= 4:                       # one-liners repeat by chance
            by_hash[r["hash"]].append(r)
    for h, rs in by_hash.items():
        if len({x["file"] for x in rs}) > 1:
            out += [{"kind": "same body", "key": h, **x} for x in rs]
    by_name = defaultdict(list)
    for r in rows:
        if not r["name"].startswith("_") and r["name"] not in {"main", "run", "__init__", "cli", "parse_args"}:
            by_name[r["name"]].append(r)
    for n, rs in by_name.items():
        if len({x["project"] for x in rs}) >= 3:
            out += [{"kind": "same name", "key": n, **x} for x in rs]
    return out


def summary(rows, dups):
    """Markdown counts per project and per topic."""
    def table(key):
        n, d = Counter(), Counter()
        for r in rows:
            n[r[key]] += 1
            d[r[key]] += r["docstring"]
        lines = [f"| {key.title()} | Functions | With docstring |", "|---|---:|---:|"]
        lines += [f"| {k} | {n[k]} | {100 * d[k] // n[k]}% |" for k, _ in n.most_common()]
        return "\n".join(lines)
    total, documented = len(rows), sum(r["docstring"] for r in rows)
    groups = len({(d["kind"], d["key"]) for d in dups})
    return (f"# Code inventory\n\n{total} functions in {len({r['file'] for r in rows})} files; "
            f"{100 * documented // max(total, 1)}% have a docstring. {groups} groups of repeated functions.\n\n"
            f"## By project\n\n{table('project')}\n\n## By topic\n\n{table('topic')}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("inventory"))
    a = ap.parse_args(argv)
    roots = [r.resolve() for r in a.roots]
    rows = scan(roots)
    dups = duplicates(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("functions.csv", rows), ("duplicates.csv", dups)):
        with open(a.out / name, "w", newline="", encoding="utf-8") as f:
            if data:
                w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                w.writeheader()
                w.writerows(data)
    (a.out / "summary.md").write_text(summary(rows, dups), encoding="utf-8")
    print((a.out / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
