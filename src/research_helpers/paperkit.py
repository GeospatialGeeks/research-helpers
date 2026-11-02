"""Shared paper helpers: recover LaTeX from Word documents, and make a two-column journal preview from one source.

    python -m research_helpers.paperkit docx2tex report.docx outdir      LaTeX and images through pandoc; the source is only read
    python -m research_helpers.paperkit preview paper/main.tex           writes and compiles paper/preview.tex
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

LAYOUTS = {"elsarticle": r"\documentclass[final,5p,times,twocolumn,authoryear]{elsarticle}"}


def docx2tex(source, outdir):
    """Convert one Word document to standalone LaTeX, with images extracted next to it."""
    source, outdir = Path(source), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "recovered.tex"
    subprocess.run(["pandoc", str(source), "-s", "-o", out.name, "--extract-media=media", "--wrap=none"], cwd=outdir, check=True, capture_output=True)
    return out


def preview(main, engine="pdflatex"):
    """Copy main.tex with its class line swapped for the journal layout, and compile. The source is unchanged."""
    main = Path(main)
    text = main.read_text(encoding="utf8")
    m = re.search(r"\\documentclass(\[[^\]]*\])?\{(\w+)\}", text)
    if not m or m[2] not in LAYOUTS:
        raise ValueError(f"no two-column layout for class {m[2] if m else 'unknown'}")
    out = main.with_name("preview.tex")
    out.write_text(text.replace(m[0], LAYOUTS[m[2]], 1), encoding="utf8")
    build(out, engine)
    return out.with_suffix(".pdf")


def build(tex, engine="pdflatex"):
    """Compile with BibTeX when a bibliography is used; returns log problems."""
    tex = Path(tex)
    run = lambda *c: subprocess.run(c, cwd=tex.parent, capture_output=True, text=True, encoding="latin1", errors="replace")
    run(engine, "-interaction=nonstopmode", tex.stem)
    if shutil.which("bibtex") and "\\bibdata" in tex.with_suffix(".aux").read_text(encoding="latin1", errors="replace"):
        run("bibtex", tex.stem)
    run(engine, "-interaction=nonstopmode", tex.stem)
    run(engine, "-interaction=nonstopmode", tex.stem)
    log = tex.with_suffix(".log").read_text(encoding="latin1", errors="replace")
    return re.findall(r"^! .*|undefined(?= on input)|Citation `[^']+' .*undefined", log, re.M)


if __name__ == "__main__":
    action, *args = sys.argv[1:]
    print({"docx2tex": docx2tex, "preview": preview, "build": build}[action](*args))
