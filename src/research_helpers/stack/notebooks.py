"""Notebooks in the stack: plain-Python sources become executed Jupyter notebooks and LaTeX cells.

A document lists its notebooks in document.toml:

    [notebooks]
    folder = "notebooks"                 # holds <name>.py in jupytext "percent" format: '# %%' code, '# %% [markdown]' text
    sources = ["climate_data"]           # run in this order
    data = "data"                        # optional: folder the notebooks read, relative to the notebooks folder
    colab = "AhmadAmmar/AhmadAmmar.github.io/blob/main/guides/<doc>/build/notebooks"   # optional: for an Open in Colab link

Building (stack.pdf and stack.web call this first, and only rerun a notebook whose source changed):
  1. <name>.py -> <name>.ipynb, executed top to bottom with the current Python (nbclient); outputs are kept.
  2. Each '# Section' heading in a markdown cell starts a section; for every section, generated/nb_<name>_<k>.tex
     holds its cells: text as LaTeX, code as an 'In [n]' listing, printed output and tables as an 'Out [n]' listing,
     figures as images. generated/nb_<name>.tex holds the whole notebook.
  3. Chapters \\input these files, so the PDF and the web show exactly the code and the results the notebook made.
  4. build/notebooks/<name>.ipynb is the executed notebook readers download (the web copies it next to the pages).
The .py file stays the one source: it diffs cleanly in git, and anyone can open the .ipynb in Jupyter or Colab.
"""
import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def _md_to_tex(md):
    r = subprocess.run([shutil.which("pandoc"), "-f", "markdown-smart", "-t", "latex", "--wrap=none", "--shift-heading-level-by=1"],
                       input=md.encode("utf8"), capture_output=True, check=True)
    tex = r.stdout.decode("utf8").replace("\r\n", "\n")
    return re.sub(r"\\label\{[^}]*\}", "", tex)


def _listing(text, lang, title):
    text = text.rstrip("\n")
    opts = f"language={lang}" + (",numbers=none" if lang == "text" else "")       # outputs carry no line numbers
    return f"\\nbprompt{{{title}}}\n\\begin{{lstlisting}}[{opts}]\n{text}\n\\end{{lstlisting}}\n"


def _strip_ansi(s):
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def cells_to_tex(nb, name, figdir):
    """LaTeX for each section of an executed notebook: [(title, tex), ...]."""
    sections, title, buf, k, fig = [], "Setup", [], 0, 0
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            # a '# Heading' line anywhere in a text cell starts a new section
            pieces = re.split(r"(?m)^# (.+)$", cell.source)
            if pieces[0].strip():
                buf.append(_md_to_tex(pieces[0]) + "\n")
            for heading, text in zip(pieces[1::2], pieces[2::2]):
                if buf or sections:
                    sections.append((title, "".join(buf)))
                title, buf = heading.strip(), []
                if text.strip():
                    buf.append(_md_to_tex(text) + "\n")
            continue
        if cell.cell_type != "code" or not cell.source.strip():
            continue
        k += 1
        buf.append(_listing(cell.source, "python", f"In [{k}]"))
        texts = []
        for o in cell.get("outputs", []):
            if o.output_type == "stream":
                texts.append(o.text)
            elif o.output_type in ("execute_result", "display_data"):
                data = o.get("data", {})
                if "image/png" in data:
                    fig += 1
                    png = f"nb_{name}_{fig:02d}.png"
                    (figdir / png).write_bytes(base64.b64decode(data["image/png"]))
                    if texts:
                        buf.append(_listing("".join(texts), "text", f"Out [{k}]")); texts = []
                    # a figure environment, so the web build places the image with the other figures
                    buf.append(f"\\nbprompt{{Out [{k}]}}\n\\begin{{figure}}[H]\\centering\\includegraphics[width=0.9\\linewidth]{{{png}}}\\end{{figure}}\n")
                elif "text/plain" in data:
                    texts.append(data["text/plain"] + "\n")
            elif o.output_type == "error":
                texts.append(_strip_ansi("\n".join(o.get("traceback", []))) + "\n")
        if texts:
            buf.append(_listing("".join(texts), "text", f"Out [{k}]"))
    if buf:
        sections.append((title, "".join(buf)))
    return sections


def build(d):
    """Run every notebook of document d whose source changed; write its LaTeX cells and the executed .ipynb."""
    nbs = d.get("notebooks")
    if not nbs:
        return []
    import jupytext
    import nbformat
    from nbclient import NotebookClient
    root, src = d["_root"], d["_src"]
    folder = root / nbs.get("folder", "notebooks")
    gen = src / "generated"
    figdir = root / d.get("figures", "figures")
    out = root / "build/notebooks"
    for p in (gen, figdir, out):
        p.mkdir(parents=True, exist_ok=True)
    made = []
    for name in nbs.get("sources", []):
        py = folder / f"{name}.py"
        digest = hashlib.sha256(py.read_bytes()).hexdigest()[:16]
        stamp = out / f"{name}.sha"
        ipynb = out / f"{name}.ipynb"
        if not (stamp.exists() and stamp.read_text() == digest and ipynb.exists()):
            nb = jupytext.read(py)
            nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
            NotebookClient(nb, timeout=nbs.get("timeout", 900), kernel_name="python3",
                           resources={"metadata": {"path": str(folder)}}).execute()
            nbformat.write(nb, ipynb)
            stamp.write_text(digest)
            print("notebook run", name, flush=True)
        nb = nbformat.read(ipynb, as_version=4)
        sections = cells_to_tex(nb, name, figdir)
        for i, (title, tex) in enumerate(sections, 1):
            (gen / f"nb_{name}_{i}.tex").write_text(tex, encoding="utf8", newline="\n")
        (gen / f"nb_{name}.tex").write_text("\n".join(f"\\section{{{t}}}\n{x}" for t, x in sections), encoding="utf8", newline="\n")
        (gen / f"nb_{name}_sections.json").write_text(json.dumps([t for t, _ in sections], indent=1), encoding="utf8")
        made.append((name, [t for t, _ in sections]))
    return made
