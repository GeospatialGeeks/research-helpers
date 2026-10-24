"""LaTeX to Word (.docx) through pandoc, with the numbering and cross-references of the PDF.

Command line:
    rh latex2docx main.tex out.docx [--csl style.csl] [--numbers generated/numbers.tex]
                  [--margins 40,25,25,25] [--font Arial] [--size 12] [--spacing 1.5] [--figure-width 15cm]

Python:
    from research_helpers.latex2docx import convert, PageSetup
    convert("thesis/main.tex", "Thesis.docx", csl="ulster-harvard-lhs.csl", page=PageSetup(left_mm=40))

Requirements: pandoc (2.11 or later) on the PATH or in RH_PANDOC.

pandoc reads LaTeX but does not number chapters, sections, tables or figures, resolve \\ref / \\cref, or read
longtable, tabularx, adjustbox, \\multicolumn, glossaries and many layout commands reliably. The converter therefore
flattens the document first:
  - every \\input / \\include / \\InputIfFileExists is inlined (relative to the main file); comments are removed;
  - headings get the numbers of the PDF: reports and books "Chapter 3. Title", "3.2 Title", "3.2.1 Title"; articles
    "2 Title", "2.1 Title"; after \\appendix "Appendix A. Title", "A.1 Title";
  - tables and figures with a caption are numbered ("Table 3.2", or "Table 4" in articles) and every \\ref, \\cref
    or \\Cref becomes a link to the bookmark of its target, with the same text as in the PDF;
  - longtable, tabularx and adjustbox become plain tabular, \\multicolumn becomes text and empty cells;
  - \\includegraphics without an extension takes the PNG beside the PDF figure (Word cannot embed PDF);
  - result macros (\\newcommand / \\renewcommand{\\Name}{value} in the --numbers files) become their values;
  - glossaries acronyms (\\newacronym) become a table of abbreviations where \\printglossary stood;
  - citations are rendered by pandoc citeproc from the .bib files named in \\bibliography, with the CSL style given
    (titles keep their capitals; pandoc would otherwise put BibTeX titles in sentence case).
A reference document with the page set-up (A4, margins, font, size, line spacing, space after paragraphs) is built
from pandoc's default by editing its XML, so Microsoft Word is not needed.
"""
import dataclasses, io, os, pathlib, re, shutil, subprocess, sys, zipfile

__all__ = ["convert", "PageSetup"]


@dataclasses.dataclass
class PageSetup:
    left_mm: float = 25
    right_mm: float = 25
    top_mm: float = 25
    bottom_mm: float = 25
    font: str = "Arial"
    size_pt: float = 12
    line_spacing: float = 1.5
    space_after_pt: float = 8
    language: str = "en-GB"


def pandoc_exe():
    p = os.environ.get("RH_PANDOC") or shutil.which("pandoc")
    if not p:
        raise SystemExit("pandoc not found: install it (https://pandoc.org/installing.html) or set RH_PANDOC")
    return p


def _bm(key):
    s = re.sub(r"[^A-Za-z0-9]", "_", key.strip())
    return ("x" + s if not s[:1].isalpha() else s)[:40]


def _strip_comments(t):
    return re.sub(r"(?<!\\)%.*", "", t)


def _inline(text, base, input_macros=("input", "include", "tabinput", "subfile")):
    def read(name):
        for c in (base / name, base / (name + ".tex")):
            if c.is_file():
                return _strip_comments(c.read_text(encoding="utf-8"))
        return ""
    text = _strip_comments(text)
    for _ in range(4):
        text = re.sub(r"\\InputIfFileExists\{([^}]+)\}\{[^}]*\}\{[^}]*\}", lambda m: read(m.group(1)), text)
        text = re.sub(r"\\(?:" + "|".join(input_macros) + r")\{([^}]+)\}", lambda m: read(m.group(1)), text)
    return text


def _group(s, i):
    """the {...} argument at or after s[i]: (content, end) or (None, i)"""
    while i < len(s) and s[i].isspace():
        i += 1
    if i >= len(s) or s[i] != "{":
        return None, i
    depth, j = 1, i + 1
    while j < len(s) and depth:
        if s[j] == "\\":
            j += 2; continue
        depth += {"{": 1, "}": -1}.get(s[j], 0); j += 1
    return s[i + 1:j - 1], j


def _conditionals(body, defs):
    r"""\IfName{a}{b} with \(re)newcommand{\IfName}[2]{#1} (or {#2}) in the definitions: keep the chosen branch"""
    picks = {k: int(v) for k, v in re.findall(r"\\(?:re)?newcommand\{\\(If[A-Za-z]+)\}\[2\]\{#(\d)\}", defs)}
    while True:
        m = next((x for x in re.finditer(r"\\(If[A-Za-z]+)(?![A-Za-z])", body) if x.group(1) in picks), None)
        if not m:
            return body
        a, j = _group(body, m.end())
        b, k = _group(body, j) if a is not None else (None, j)
        if b is None:
            return body
        body = body[:m.start()] + (a if picks[m.group(1)] == 1 else b) + body[k:]


def _tables(body):
    def lt_fix(m):
        spec, b = m.group(1), m.group(2)
        cap = re.search(r"\\caption\{(.*?)\}\\label\{([^}]*)\}", b, re.S)
        head = b.split(r"\endfirsthead", 1)[0]
        head = head[head.index(r"\toprule"):] if r"\toprule" in head else ""
        b = b.split(r"\endhead", 1)[1] if r"\endhead" in b else b
        c = (r"\caption{" + cap.group(1) + r"}\label{" + cap.group(2) + "}\n") if cap else ""
        return r"\begin{table}" + "\n" + c + r"\begin{tabular}{" + spec + "}\n" + head + b + r"\end{tabular}" + "\n" + r"\end{table}"
    body = re.sub(r"\\begin\{longtable\}\{((?:[^{}]|\{[^{}]*\})*)\}(.*?)\\end\{longtable\}", lt_fix, body, flags=re.S)
    body = re.sub(r"\\begin\{adjustbox\}\{[^}]*\}|\\end\{adjustbox\}|\\resizebox\{[^}]*\}\{[^}]*\}", "", body)
    body = re.sub(r"\\multicolumn\{(\d+)\}\{(?:[^{}]|\{[^{}]*\})*\}\{((?:[^{}]|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*)\}",
                  lambda m: m.group(2) + " &" * (int(m.group(1)) - 1), body)

    def to_tabular(m):
        spec = re.sub(r"@\{(?:[^{}]|\{[^{}]*\})*\}", "", m.group(1))
        spec = re.sub(r"[pmPb]\{[^}]*\}", "l", spec)
        spec = re.sub(r">\{[^}]*\}|<\{[^}]*\}", "", spec)
        return r"\begin{tabular}{%s}" % "".join("l" if c in "lXYp" else c for c in spec if c in "lcrXYp")
    body = re.sub(r"\\begin\{tabularx\}\{[^}]*\}\{((?:[^{}]|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*)\}", to_tabular, body)
    body = body.replace(r"\end{tabularx}", r"\end{tabular}")
    return re.sub(r"\\begin\{tabular\}\{((?:[^{}]|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*)\}", to_tabular, body)


def _number(body, chapters):
    """number headings and floats, return (body, {label: shown name})"""
    names, c = {}, {"chap": 0, "app": 0, "sec": 0, "sub": 0, "subsub": 0, "table": 0, "figure": 0}
    in_app = False
    out, pos = [], 0
    pat = re.compile(r"\\appendix\b|\\(chapter|section|subsection|subsubsection)(\*?)\{([^}]*)\}((?:\\crefalias\{[^}]*\}\{[^}]*\})?\\label\{([^}]+)\})?"
                     r"|\\begin\{(table|figure)\*?\}(.*?)\\end\{\6\*?\}", re.S)
    for m in pat.finditer(body):
        out.append(body[pos:m.start()]); pos = m.end()
        if m.group(0).startswith(r"\appendix"):
            in_app = True; c.update(sec=0, chap=c["chap"]); continue
        if m.group(6):
            kind, content = m.group(6), m.group(7)
            if r"\caption" not in content:
                out.append(m.group(0)); continue
            c[kind] += 1
            if chapters:
                top = chr(64 + c["app"]) if in_app else str(c["chap"])
                name = f"{'Table' if kind == 'table' else 'Figure'} {top}.{c[kind]}"
            else:
                name = f"{'Table' if kind == 'table' else 'Figure'} {c[kind]}"
            lab = re.search(r"\\label\{([^}]+)\}", content)
            if lab:
                names[lab.group(1)] = name
            out.append(r"\begin{%s}%s\end{%s}" % (kind, content.replace(r"\caption{", r"\caption{" + name + ". ", 1), kind)); continue
        kind, star, title, lab = m.group(1), m.group(2), m.group(3), m.group(5)
        if star:
            out.append(m.group(0)); continue
        top_level = "chapter" if chapters else "section"
        if kind == top_level:
            if in_app:
                c["app"] += 1; num = chr(64 + c["app"]); shown = f"Appendix {num}. {title}"; name = f"Appendix {num}"
            else:
                key = "chap" if chapters else "sec"
                c[key] += 1; num = str(c[key])
                shown = f"Chapter {num}. {title}" if chapters else f"{num} {title}"
                name = f"Chapter {num}" if chapters else f"Section {num}"
            if chapters:
                c.update(sec=0, sub=0, table=0, figure=0)
            else:
                c.update(sub=0, subsub=0)
            head = "section"
        else:
            top = chr(64 + c["app"]) if in_app else str(c["chap"] if chapters else c["sec"])
            if chapters and kind == "section":
                c["sec"] += 1; c["sub"] = 0; num = f"{top}.{c['sec']}"; head = "subsection"
            elif (chapters and kind == "subsection") or (not chapters and kind == "subsection"):
                if chapters:
                    c["sub"] += 1; num = f"{top}.{c['sec']}.{c['sub']}"; head = "subsubsection"
                else:
                    c["sub"] += 1; c["subsub"] = 0; num = f"{top}.{c['sub']}"; head = "subsection"
            elif not chapters and kind == "subsubsection":
                c["subsub"] += 1; num = f"{top}.{c['sub']}.{c['subsub']}"; head = "subsubsection"
            else:
                out.append(f"\\paragraph{{{title}}}" + (f"\\label{{{lab}}}" if lab else "")); continue
            shown, name = f"{num} {title}", f"Section {num}"
        if lab:
            names[lab] = name
        out.append(f"\\{head}*{{{shown}}}" + (f"\\label{{{lab}}}" if lab else ""))
    out.append(body[pos:])
    return "".join(out).replace(r"\chapter*{", r"\section*{"), names


def reference_doc(dest, page, pandoc=None):
    """pandoc's default reference.docx with the page set-up written into its XML"""
    raw = subprocess.run([pandoc or pandoc_exe(), "--print-default-data-file", "reference.docx"], capture_output=True).stdout
    zin, buf = zipfile.ZipFile(io.BytesIO(raw)), io.BytesIO()
    tw = lambda mm: int(round(mm * 56.6929))                       # twentieths of a point
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                s = data.decode("utf-8")
                f = page.font
                s = re.sub(r"<w:rFonts [^>]*/>", f'<w:rFonts w:ascii="{f}" w:hAnsi="{f}" w:eastAsia="{f}" w:cs="{f}" />', s)
                s = s.replace('w:val="en-US"', f'w:val="{page.language}"')
                s = re.sub(r'(<w:rPrDefault>.*?<w:sz w:val=")\d+(")', lambda m: m.group(1) + str(int(page.size_pt * 2)) + m.group(2), s, count=1, flags=re.S)
                s = re.sub(r'(<w:rPrDefault>.*?<w:szCs w:val=")\d+(")', lambda m: m.group(1) + str(int(page.size_pt * 2)) + m.group(2), s, count=1, flags=re.S)
                i = s.find("<w:pPrDefault>"); j = s.find("<w:spacing", i)
                if i != -1 and j != -1:
                    k = s.find("/>", j) + 2
                    s = s[:j] + f'<w:spacing w:after="{int(page.space_after_pt * 20)}" w:line="{int(240 * page.line_spacing)}" w:lineRule="auto" />' + s[k:]
                data = s.encode("utf-8")
            if item.filename == "word/document.xml":
                s = data.decode("utf-8")
                sect = (f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="{tw(page.top_mm)}" w:right="{tw(page.right_mm)}" '
                        f'w:bottom="{tw(page.bottom_mm)}" w:left="{tw(page.left_mm)}" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')
                s = re.sub(r"<w:sectPr.*?</w:sectPr>|<w:sectPr\s*/>", sect, s, count=1, flags=re.S) if "<w:sectPr" in s \
                    else s.replace("</w:body>", sect + "</w:body>")
                data = s.encode("utf-8")
            zout.writestr(item, data)
    pathlib.Path(dest).write_bytes(buf.getvalue())


def convert(main_tex, out_docx, csl=None, numbers=(), page=None, figure_width="15cm", front_matter="", keep_intermediate=False):
    """Convert main_tex (and everything it inputs) to out_docx. Returns pandoc's exit code."""
    main_tex, out = pathlib.Path(main_tex).resolve(), pathlib.Path(out_docx).resolve()
    base, page = main_tex.parent, page or PageSetup()
    src = main_tex.read_text(encoding="utf-8")
    pre, body = src.split(r"\begin{document}", 1)
    body = body.split(r"\end{document}", 1)[0]
    chapters = bool(re.search(r"\\documentclass(\[[^\]]*\])?\{(report|book|memoir|scrreprt|scrbook)\}", pre))
    abbr = _inline(pre, base)                                           # preamble inputs (abbreviations, macros)
    body = _inline(body, base)

    defs = "\n".join(pathlib.Path(f).read_text(encoding="utf-8") for f in numbers if pathlib.Path(f).exists()) + abbr
    body = _conditionals(body, defs)                                    # \IfName{a}{b} switched in the definitions
    body = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", body, flags=re.S)
    body = re.sub(r"\\(begin|end)\{(frontmatter|graphicalabstract)\}", "", body)        # journal front matter (elsarticle)
    body = re.sub(r"\\begin\{highlights\}(.*?)\\end\{highlights\}",
                  lambda m: "\\section*{Highlights}\n\\begin{itemize}" + m.group(1) + "\\end{itemize}", body, flags=re.S)
    body = re.sub(r"\\begin\{keyword\}(.*?)\\end\{keyword\}",
                  lambda m: "\\textbf{Keywords:} " + m.group(1).replace("\\sep", ";"), body, flags=re.S)
    body = re.sub(r"\\(linenumbers|nolinenumbers)\b", "", body)
    body = re.sub(r"\\(tableofcontents|listoffigures|listoftables|clearpage|cleardoublepage|newpage|FloatBarrier|centering|glsaddall|onehalfspacing|doublespacing|maketitle)\b", "", body)
    body = re.sub(r"\\pagenumbering\{[^}]*\}|\\addcontentsline\{[^}]*\}\{[^}]*\}\{[^}]*\}|\\vspace\*?\{[^}]*\}|\\vfill|\\needspace\{[^}]*\}", "", body)
    acr = re.findall(r"\\newacronym(?:\[[^\]]*\])?\{[^}]*\}\{(.*?)\}\{(.*?)\}\s*$", abbr, re.M)
    if acr:
        rows = "\n".join(f"{s} & {l} \\\\" for s, l in acr)
        body = re.sub(r"\\printglossary(\[[^\]]*\])?|\\printacronyms(\[[^\]]*\])?",
                      lambda m: "\\section*{Abbreviations}\n\\begin{tabular}{ll}\n" + rows + "\n\\end{tabular}\n", body)
    body = _tables(body)
    body = re.sub(r"\\par\\smallskip\\parbox\{[^}]*\}\{\\footnotesize (.*?)\}\n", r"\n\\emph{Note.} \1\n", body)
    body = re.sub(r"\\(tiny|scriptsize|footnotesize|small|normalsize)\b", "", body)
    body = re.sub(r"\\fbox\{\\parbox\{[^}]*\}\{(.*?)\}\}", r"\1", body, flags=re.S)
    body = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}.]+)\}", lambda m: r"\includegraphics[width=" + figure_width + "]{" + m.group(2) + ".png}", body)

    body = re.sub(r"\\label\[[^\]]*\]", lambda m: "\\label", body)          # cleveref \label[type]{key}
    body = re.sub(r"\\label\{([^}]+)\}", lambda m: "\\label{" + _bm(m.group(1)) + "}", body)
    body = re.sub(r"\\([cC]?ref|autoref)\{([^}]+)\}", lambda m: "\\" + m.group(1) + "{" + ",".join(_bm(k) for k in m.group(2).split(",")) + "}", body)
    body, names = _number(body, chapters)

    def resolve(m):
        keys = [k.strip() for k in m.group(2).split(",")]
        parts = [r"\hyperref[%s]{%s}" % (k, names.get(k, k)) for k in keys]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    body = re.sub(r"\\([cC]?ref|autoref)\{([^}]+)\}", resolve, body)

    vals = {}
    for f in numbers:
        t = pathlib.Path(f).read_text(encoding="utf-8") if pathlib.Path(f).exists() else ""
        vals.update(dict(re.findall(r"\\(?:re)?newcommand\{\\([A-Za-z]+)\}\{(.*?)\}\s*$", t, re.M)))
    vals.update(dict(re.findall(r"\\(?:re)?newcommand\{\\([A-Za-z]+)\}\{([^{}#]*)\}\s*$", abbr, re.M)))
    vals = {k: v for k, v in vals.items() if not k.startswith("If")}
    for k in sorted(vals, key=len, reverse=True):
        body = re.sub(r"\\" + k + r"(\{\})?(?![A-Za-z])", lambda m, v=vals[k]: v, body)
    body = re.sub(r"\\bibliographystyle\{[^}]*\}\s*\\bibliography\{[^}]*\}|\\printbibliography(\[[^\]]*\])?",
                  r"\\section*{References}\n\\hypertarget{refs}{}\n", body)

    title = re.search(r"\\title\{(.*?)\}", pre + body, re.S)
    tmp_dir = out.parent
    tex = "\\documentclass{article}\n\\begin{document}\n" + front_matter + body + "\n\\end{document}\n"
    tmp = out.with_suffix(".pandoc.tex"); tmp.write_text(tex, encoding="utf-8")
    bibs = []
    m = re.search(r"\\bibliography\{([^}]*)\}", src) or re.search(r"\\addbibresource\{([^}]*)\}", pre)
    for b in (m.group(1).split(",") if m else []):
        p = base / (b.strip() if b.strip().endswith(".bib") else b.strip() + ".bib")
        if p.exists():
            t = re.sub(r"(\btitle\s*=\s*)\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1{{\2}}", p.read_text(encoding="utf-8"))
            q = tmp_dir / f"_{p.stem}.bib"; q.write_text(t, encoding="utf-8"); bibs.append(q)
    ref = tmp_dir / "_reference.docx"; pandoc = pandoc_exe(); reference_doc(ref, page, pandoc)
    figs = [base / "figures", base] + [base / p for p in re.findall(r"\{([^{}]+/)\}", (re.search(r"\\graphicspath\{(.*?)\}\s*$", pre, re.M) or [None, ""])[1])]
    cmd = [pandoc, str(tmp), "-f", "latex", "-t", "docx", "-o", str(out), "--resource-path", os.pathsep.join(str(f) for f in figs),
           "--reference-doc", str(ref), "--metadata", f"lang={page.language}", "--metadata", "link-citations=true"]
    if title:
        cmd += ["--metadata", "title=" + re.sub(r"\\\\|\s+", " ", title.group(1)).strip()]
    if bibs:
        cmd += ["--citeproc"] + sum([["--bibliography", str(b)] for b in bibs], [])
    if csl:
        cmd += ["--csl", str(csl)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if not keep_intermediate:
        for f in [tmp, ref] + bibs:
            f.unlink(missing_ok=True)
    missing = sorted(set(re.findall(r"\\hyperref\[([^\]]+)\]\{\1\}", body)))
    if r.returncode or missing:
        print(f"pandoc exit {r.returncode}; " + (r.stderr or "")[:1500])
    if missing:
        print("references without a target:", ", ".join(missing))
    return r.returncode
