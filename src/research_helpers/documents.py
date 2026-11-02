"""One table of document types, so that every project starts, builds and names its files the same way.

    python -m research_helpers.documents list
    python -m research_helpers.documents new elsevier D:/path/14_Short_Name
    python -m research_helpers.documents build D:/path/14_Short_Name

Each type sets the template, the engine, what it builds, and whether it may go online.
"""
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocType:
    about: str
    starter: str            # rh template starter, or the name of a skeleton below
    engine: str
    outputs: tuple          # main, preview, docx, web, story, slides
    public: bool            # may source and outputs be public?
    folder: str = "paper"


TYPES = {
    "elsevier": DocType("Journal paper, Harvard citations, with a two-column preview", "elsevier", "pdflatex", ("main", "preview", "docx"), False),
    "ieee": DocType("IEEE conference or journal paper", "ieee-conference", "pdflatex", ("main", "docx"), False),
    "ec3": DocType("EC3 paper", "ec3-paper", "pdflatex", ("main",), False),
    "ulster-thesis": DocType("Ulster thesis, from the ulster-thesis-template repository", "ulster-thesis", "xelatex", ("main",), False, "latex"),
    "report": DocType("Private working record or audit", "skeleton", "pdflatex", ("main",), False, "docs"),
    "tutorial": DocType("Public guide, as a PDF and pages on ahmadammar.github.io", "skeleton", "pdflatex", ("main", "web"), True, "tex"),
    "documentation": DocType("Public documentation of a tool, as a PDF and pages", "skeleton", "pdflatex", ("main", "web"), True, "tex"),
    "poster": DocType("Conference poster", "latex-poster", "xelatex", ("main",), False, "poster"),
}
SKELETON = r"""\documentclass[11pt,a4paper]{report}
\usepackage[T1]{fontenc}
\usepackage{lmodern,amsmath,graphicx,booktabs,xcolor,listings,float,tabularx}
\usepackage[margin=24mm]{geometry}
\usepackage[hidelinks]{hyperref}
\graphicspath{{../figures/}}
\lstset{basicstyle=\ttfamily\scriptsize,breaklines=true,columns=fullflexible,frame=single,showstringspaces=false}
\newcommand{\snippetcaption}[1]{\par\smallskip\noindent{\footnotesize\textbf{From the code:} \texttt{#1}}\par\nopagebreak}
\title{TITLE}
\author{Ahmad Ammar}
\date{}
\begin{document}
\maketitle
\tableofcontents
\chapter{Start}
\end{document}
"""
FOLDERS = ("figures", "tables", "code", "releases")
IGNORE = "*.aux\n*.log\n*.out\n*.toc\n*.bbl\n*.blg\n*.spl\n*.fls\n*.fdb_latexmk\nweb_figs.*\n"


def new(kind, folder):
    t, d = TYPES[kind], Path(folder)
    if kind == "ulster-thesis" or t.starter == "latex-poster":
        raise SystemExit(f"{kind}: start from its own template, then add .doctype")
    src = d / t.folder
    for f in (*FOLDERS, f"{t.folder}/generated"):
        (d / f).mkdir(parents=True, exist_ok=True)
    if t.starter == "skeleton":
        if not (src / "main.tex").exists():
            (src / "main.tex").write_text(SKELETON, encoding="utf8")
    elif not (src / "main.tex").exists():
        subprocess.run(["rh", "template", "new", t.starter, str(src)], check=True)
    (d / ".doctype").write_text(kind + "\n")
    for path, text in ((d / ".gitignore", IGNORE), (d / "README.md", f"# {d.name}\n\n{t.about}.\n")):
        if not path.exists():
            path.write_text(text)
    if not (d / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)


def build(folder):
    from .paperkit import build as compile_tex, preview
    d = Path(folder)
    t = TYPES[(d / ".doctype").read_text().strip()]
    main = d / t.folder / "main.tex"
    print("main", compile_tex(main, t.engine)[:6])
    if "preview" in t.outputs:
        print("preview", preview(main, t.engine))
    if "docx" in t.outputs and shutil.which("rh"):
        subprocess.run(["rh", "latex2docx", str(main)], check=False)


if __name__ == "__main__":
    action, *args = sys.argv[1:] or ["list"]
    if action == "list":
        for k, v in TYPES.items():
            print(f"{k:15} {'public' if v.public else 'private':8} {','.join(v.outputs):22} {v.about}")
    else:
        {"new": new, "build": build}[action](*args)
