"""LaTeX to Word (.docx) through pandoc, with the numbering and cross-references of the PDF.

Command line:
    rh latex2docx main.tex out.docx [--csl style.csl] [--numbers generated/numbers.tex]
                  [--margins 40,25,25,25] [--font Arial] [--size 12] [--spacing 1.5] [--figure-width 15cm]
    rh latex2docx paper.tex paper.docx --csl ieee.csl --profile ieee      IEEE conference paper on IEEE's Word template

Python:
    from research_helpers.latex2docx import convert, PageSetup, TitlePage, ieee_profile
    convert("thesis/main.tex", "Thesis.docx", csl="ulster-harvard-lhs.csl", page=PageSetup(left_mm=40),
            front_matter=title_page_latex, title_page=TitlePage())
    convert("paper/main.tex", "paper.docx", csl="ieee.csl", profile=ieee_profile())

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
  - a figure that exists only as PDF is rendered to PNG (pdftoppm, or PyMuPDF), at the width it has in the PDF.
A reference document is built from pandoc's default by editing its XML, so Microsoft Word is not needed: page set-up
(margins, font, size, line spacing, paragraph spacing, justified text), headings at the sizes of the LaTeX class, each
chapter on a new page, booktabs tables (rules above, below and under the header, single-spaced rows), captions with
bold labels, a reference list with hanging indent, and page numbers in the header. After pandoc, the Word XML gets the
contents and lists of figures and tables as Word fields, a title page laid out like the PDF's (TitlePage), no page
number on it, roman page numbers for the preliminary pages and arabic from the main matter.

Publisher templates: with a Profile (e.g. ieee_profile()), the publisher's Word template supplies the styles and page
set-up; pandoc's styles are mapped onto the template's, the text is set in its columns after the title block, and
headings, captions and references are left for the template to number ("I. Introduction", "Fig. 1.", "[1]").
"""
import dataclasses, io, os, pathlib, re, shutil, subprocess, sys, zipfile

__all__ = ["convert", "PageSetup", "TitlePage", "Profile", "ieee_profile"]


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
    heading_color: str = "000000"        # hex; "" keeps pandoc's blue headings
    link_color: str = "000073"           # hex; matches hyperref's blue!45!black
    page_number: str = "right"           # page number in the header: "right", "center" or "" for none
    justify: bool = True                 # body text justified, as in the PDF
    caption_size_pt: float = 11          # \small captions of a 12 pt document
    table_size_pt: float = 0             # 0: body size
    booktabs: bool = True                # tables with top, header and bottom rules only, single-spaced rows


@dataclasses.dataclass
class TitlePage:
    """Layout of the front matter given to convert(front_matter=...): one paragraph per item, centred.
    sizes_pt: font sizes of the first paragraphs (title, author, ...); gaps_mm: space above each paragraph;
    bottom: number of trailing paragraphs set at the foot of the page (e.g. a word-count statement);
    numbered: show a page number on the title page."""
    sizes_pt: tuple = (17.28, 14.4)
    gaps_mm: tuple = (0, 20, 15, 10, 10)
    bottom: int = 1
    numbered: bool = False


@dataclasses.dataclass
class Profile:
    """A publisher's Word template and how the converted paper maps onto it.
    styles: pandoc paragraph style id -> template style id; columns: text columns after the title block;
    number_headings / caption_labels: False when the template numbers headings / captions itself (then the numbers are
    left out of the text); *_name: how cross-references name sections, figures and tables ({n} number, {r} roman);
    strip_reference_numbers: remove "[1]" from reference-list entries when the template's style numbers them;
    column_width_cm / text_width_cm: widths for \\columnwidth and \\textwidth figures."""
    reference_docx: str
    styles: dict = dataclasses.field(default_factory=dict)
    columns: int = 1
    column_space_pt: float = 18
    number_headings: bool = True
    caption_labels: bool = True
    section_name: str = "Section {n}"
    figure_name: str = "Figure {n}"
    table_name: str = "Table {n}"
    strip_reference_numbers: bool = False
    abstract_label: str = ""
    keywords_label: str = ""
    column_width_cm: float = 0
    text_width_cm: float = 0


def ieee_profile(reference_docx=None):
    """IEEE conference paper (A4 by default) on IEEE's own Word template: two columns, headings I / A numbered by the
    template, "Fig. 1." and "TABLE I" captions and numbered references from its styles. The template is taken from the
    research-helpers template library (rh template fetch igarss-2026) unless given."""
    if reference_docx is None:
        from .templates import library
        hits = sorted(library().rglob("conference-template-a4.docx"))
        if not hits:
            raise SystemExit("IEEE Word template not found: run `rh template fetch igarss-2026` or give reference_docx")
        reference_docx = hits[-1]
    return Profile(reference_docx=str(reference_docx), columns=2, column_space_pt=18, number_headings=False, caption_labels=False,
                   styles={"Title": "papertitle", "FirstParagraph": "BodyText", "BodyText": "BodyText", "ImageCaption": "figurecaption",
                           "TableCaption": "tablehead", "Bibliography": "references", "Compact": "tablecopy",
                           "CaptionedFigure": "Normal", "Figure": "Normal"},
                   section_name="Section {n}", figure_name="Fig. {n}", table_name="Table {r}", strip_reference_numbers=True,
                   abstract_label="Abstract", keywords_label="Index Terms", column_width_cm=8.6, text_width_cm=17.8)


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


def _roman(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
                 (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s; n -= v
    return out


def _number(body, chapters, profile=None):
    """number headings and floats, return (body, {label: shown name}). With a publisher profile whose Word template
    numbers headings and captions itself, the numbers are left out of the text and only used for cross-references."""
    if profile is not None and not (profile.number_headings and profile.caption_labels):
        return _number_profile(body, profile)
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
            out.append(r"\begin{%s}%s\end{%s}" % (kind, content.replace(r"\caption{", r"\caption{\textbf{" + name + ":} ", 1), kind)); continue
        kind, star, title, lab = m.group(1), m.group(2), m.group(3), m.group(5)
        if star:
            out.append(m.group(0)); continue
        top_level = "chapter" if chapters else "section"
        if kind == top_level:
            if in_app:
                c["app"] += 1; num = chr(64 + c["app"]); name = f"Appendix {num}"
                shown = f"Appendix {num}{_BR}{title}" if chapters else f"Appendix {num}. {title}"
            else:
                key = "chap" if chapters else "sec"
                c[key] += 1; num = str(c[key])
                shown = f"Chapter {num}{_BR}{title}" if chapters else f"{num} {title}"
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


def _number_profile(body, profile):
    """articles in a publisher's template that numbers headings, figures and tables itself (IEEE: I, A; Fig. 1;
    TABLE I): headings and captions stay unnumbered in the text, cross-references get the publisher's names"""
    names, c = {}, {"sec": 0, "sub": 0, "table": 0, "figure": 0}
    out, pos = [], 0
    pat = re.compile(r"\\(section|subsection|subsubsection)(\*?)\{([^}]*)\}(\\label\{([^}]+)\})?"
                     r"|\\begin\{(table|figure)(\*?)\}(.*?)\\end\{\6\*?\}", re.S)
    for m in pat.finditer(body):
        out.append(body[pos:m.start()]); pos = m.end()
        if m.group(6):
            kind, content = m.group(6), m.group(8)
            if r"\caption" in content:
                c[kind] += 1
                n = c[kind]
                fmt = profile.figure_name if kind == "figure" else profile.table_name
                lab = re.search(r"\\label\{([^}]+)\}", content)
                if lab:
                    names[lab.group(1)] = fmt.format(n=n, r=_roman(n))
                if profile.caption_labels:
                    content = content.replace(r"\caption{", r"\caption{" + fmt.format(n=n, r=_roman(n)) + ". ", 1)
            out.append(r"\begin{%s}%s\end{%s}" % (kind, content, kind)); continue
        kind, star, title, lab = m.group(1), m.group(2), m.group(3), m.group(5)
        if not star:
            if kind == "section":
                c["sec"] += 1; c["sub"] = 0; num = _roman(c["sec"])
            else:
                c["sub"] += 1; num = f"{_roman(c['sec'])}-{chr(64 + c['sub'])}" if kind == "subsection" else f"{_roman(c['sec'])}"
            if lab:
                names[lab] = profile.section_name.format(n=num)
        head = {"section": "section", "subsection": "subsection", "subsubsection": "subsubsection"}[kind]
        out.append(f"\\{head}{{{title}}}" + (f"\\label{{{lab}}}" if lab else ""))
    out.append(body[pos:])
    return "".join(out), names


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _style(s, style_id, fn):
    """apply fn to the XML of one style in styles.xml"""
    return re.sub(r'<w:style [^>]*w:styleId="%s".*?</w:style>' % style_id, lambda m: fn(m.group(0)), s, count=1, flags=re.S)


def _set_color(xml, color):
    xml = re.sub(r"<w:color [^>]*/>", "", xml)
    return re.sub(r"<w:rPr>", f'<w:rPr><w:color w:val="{color}" />', xml, count=1) if "<w:rPr>" in xml \
        else xml.replace("</w:style>", f'<w:rPr><w:color w:val="{color}" /></w:rPr></w:style>')


def _page_break_before(xml):
    if "<w:pageBreakBefore" in xml:
        return xml
    if "<w:pPr>" in xml:
        return xml.replace("<w:pPr>", "<w:pPr><w:pageBreakBefore />", 1)
    at = "<w:rPr>" if "<w:rPr>" in xml else "</w:style>"
    return xml.replace(at, "<w:pPr><w:pageBreakBefore /></w:pPr>" + at, 1)


def _set_ppr(xml, ppr):
    """replace a style's paragraph properties"""
    xml = re.sub(r"<w:pPr\s*/>|<w:pPr>.*?</w:pPr>", "", xml, flags=re.S)
    return re.sub(r"(</w:name>|<w:name [^>]*/>)((?:\s*<w:(?:basedOn|next|link|uiPriority|semiHidden|unhideWhenUsed|qFormat)[^>]*/>)*)",
                  lambda m: m.group(1) + m.group(2) + ppr, xml, count=1)


def _set_rpr(xml, rpr):
    xml = re.sub(r"<w:rPr\s*/>|<w:rPr>.*?</w:rPr>", "", xml, flags=re.S)
    return xml.replace("</w:style>", rpr + "</w:style>")


def _paragraph_styles(s, page, chapters=False):
    """body text, captions, table cells, tables and the reference list closer to the PDF"""
    after = int(page.space_after_pt * 20)
    jc = '<w:jc w:val="both"/>' if page.justify else ""
    for sid in ("BodyText", "FirstParagraph"):
        s = _style(s, sid, lambda x: _set_ppr(x, f'<w:pPr><w:spacing w:before="0" w:after="{after}"/>{jc}</w:pPr>'))
    cap = f'<w:rPr><w:sz w:val="{int(page.caption_size_pt * 2)}"/><w:szCs w:val="{int(page.caption_size_pt * 2)}"/></w:rPr>'
    s = _style(s, "Caption", lambda x: _set_rpr(_set_ppr(x, '<w:pPr><w:spacing w:before="120" w:after="200" w:line="240" '
                                                           'w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'), cap))
    s = _style(s, "TableCaption", lambda x: _set_ppr(x, '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120" '
                                                        'w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'))
    s = _style(s, "ImageCaption", lambda x: _set_ppr(x, '<w:pPr><w:spacing w:before="60" w:after="240" w:line="240" '
                                                        'w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'))
    s = _style(s, "Figure", lambda x: _set_ppr(x, '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="0"/>'
                                                  '<w:jc w:val="center"/></w:pPr>'))
    s = _style(s, "CaptionedFigure", lambda x: _set_ppr(x, '<w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr>'))
    if page.booktabs:
        cell = '<w:pPr><w:spacing w:before="30" w:after="30" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>'
        if page.table_size_pt:
            cell += f'<w:rPr><w:sz w:val="{int(page.table_size_pt * 2)}"/></w:rPr>'
        s = _style(s, "Compact", lambda x: _set_ppr(re.sub(r"<w:rPr>.*?</w:rPr>", "", x, flags=re.S), cell))
        rule = lambda side, sz: f'<w:{side} w:val="single" w:sz="{sz}" w:space="0" w:color="000000"/>'
        table = ('<w:style w:type="table" w:default="1" w:styleId="Table"><w:name w:val="Table"/><w:basedOn w:val="TableNormal"/>'
                 '<w:uiPriority w:val="59"/><w:qFormat/><w:tblPr><w:jc w:val="center"/><w:tblInd w:w="0" w:type="dxa"/>'
                 f'<w:tblBorders>{rule("top", 8)}{rule("bottom", 8)}</w:tblBorders><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
                 '<w:left w:w="115" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="115" w:type="dxa"/></w:tblCellMar>'
                 '</w:tblPr><w:tblStylePr w:type="firstRow"><w:tcPr>'
                 f'<w:tcBorders>{rule("bottom", 5)}</w:tcBorders><w:vAlign w:val="bottom"/></w:tcPr></w:tblStylePr></w:style>')
        s = re.sub(r'<w:style [^>]*w:styleId="Table".*?</w:style>', lambda _: table, s, count=1, flags=re.S)
    s = _style(s, "Bibliography", lambda x: _set_ppr(x, f'<w:pPr><w:spacing w:before="0" w:after="{after}"/>'
                                                        '<w:ind w:left="567" w:hanging="567"/></w:pPr>'))
    # headings at the sizes of the LaTeX classes (12 pt): report chapter 24.9 pt, section 14.4 pt, subsection 12 pt;
    # article section 14.4 pt, subsection 12 pt
    color = f'<w:color w:val="{page.heading_color}"/>' if page.heading_color else ""
    sizes = (("Heading1", 50, 1000, 600, 0), ("Heading2", 29, 360, 160, 1), ("Heading3", 24, 280, 120, 2)) if chapters else \
            (("Heading1", 29, 360, 160, 0), ("Heading2", 24, 280, 120, 1), ("Heading3", 24, 240, 120, 2))
    for sid, sz, before, after, outline in sizes:
        s = _style(s, sid, lambda x, sz=sz, b=before, a=after, o=outline: _set_rpr(_set_ppr(x,
                   f'<w:pPr><w:keepNext/><w:keepLines/>{"<w:pageBreakBefore/>" if "<w:pageBreakBefore" in x else ""}'
                   f'<w:spacing w:before="{b}" w:after="{a}" w:line="240" w:lineRule="auto"/><w:outlineLvl w:val="{o}"/></w:pPr>'),
                   f'<w:rPr><w:b/><w:bCs/>{color}<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'))
    h1 = re.search(r'<w:style [^>]*w:styleId="Heading1".*?(<w:rPr>.*?</w:rPr>)', s, re.S)
    if h1:
        gap = '<w:spacing w:before="1000" w:after="600"/>' if chapters else '<w:spacing w:before="360" w:after="160"/>'
        # outline level 9 (body text): "Contents" and the list titles are not themselves listed in the contents
        s = _style(s, "TOCHeading", lambda x: _set_rpr(_set_ppr(x, f'<w:pPr><w:keepNext/>{gap}<w:outlineLvl w:val="9"/></w:pPr>'),
                                                       h1.group(1)))
    # contents: chapters bold, sections indented, as in the LaTeX contents
    toc = "".join(
        f'<w:style w:type="paragraph" w:styleId="TOC{n}"><w:name w:val="toc {n}"/><w:basedOn w:val="Normal"/>'
        f'<w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:tabs><w:tab w:val="right" '
        f'w:leader="dot" w:pos="{int(round((210 - page.left_mm - page.right_mm) * 56.6929)) - 10}"/></w:tabs>'
        f'<w:spacing w:before="{b}" w:after="0" w:line="276" w:lineRule="auto"/><w:ind w:left="{ind}"/></w:pPr>'
        f'{"<w:rPr><w:b/><w:bCs/></w:rPr>" if n == 1 else ""}</w:style>' for n, b, ind in ((1, 160, 0), (2, 0, 360), (3, 0, 720)))
    s = re.sub(r'<w:style [^>]*w:styleId="TOC[123]".*?</w:style>', "", s, flags=re.S).replace("</w:styles>", toc + "</w:styles>")
    return s


def reference_doc(dest, page, pandoc=None, chapters=False):
    """pandoc's default reference.docx with the page set-up written into its XML: margins, font, size, spacing,
    heading and link colours, a page number in the header and, for chapter documents, each top-level heading on a
    new page"""
    raw = subprocess.run([pandoc or pandoc_exe(), "--print-default-data-file", "reference.docx"], capture_output=True).stdout
    zin, buf = zipfile.ZipFile(io.BytesIO(raw)), io.BytesIO()
    tw = lambda mm: int(round(mm * 56.6929))                       # twentieths of a point
    jc = {"right": "right", "center": "center", "centre": "center"}.get(page.page_number or "")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml" and jc:
                data = data.decode("utf-8").replace("</Types>", '<Override PartName="/word/header1.xml" ContentType='
                    '"application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>').encode("utf-8")
            if item.filename == "word/_rels/document.xml.rels" and jc:
                data = data.decode("utf-8").replace("</Relationships>", '<Relationship Id="rIdRhHeader1" Type='
                    '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
                    "</Relationships>").encode("utf-8")
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
                if page.heading_color:
                    for sid in ["Title", "Subtitle", "TOCHeading"] + [f"Heading{n}" for n in range(1, 10)]:
                        s = _style(s, sid, lambda x: _set_color(x, page.heading_color))
                if page.link_color:
                    s = _style(s, "Hyperlink", lambda x: _set_color(x, page.link_color))
                if chapters:
                    s = _style(s, "Heading1", _page_break_before)
                s = _paragraph_styles(s, page, chapters)
                data = s.encode("utf-8")
            if item.filename == "word/document.xml":
                s = data.decode("utf-8")
                hdr = '<w:headerReference w:type="default" r:id="rIdRhHeader1"/>' if jc else ""
                sect = (f'<w:sectPr>{hdr}<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="{tw(page.top_mm)}" w:right="{tw(page.right_mm)}" '
                        f'w:bottom="{tw(page.bottom_mm)}" w:left="{tw(page.left_mm)}" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>')
                s = re.sub(r"<w:sectPr.*?</w:sectPr>|<w:sectPr\s*/>", sect, s, count=1, flags=re.S) if "<w:sectPr" in s \
                    else s.replace("</w:body>", sect + "</w:body>")
                if jc and "xmlns:r=" not in s[:2000]:
                    s = s.replace("<w:document ", '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ', 1)
                data = s.encode("utf-8")
            zout.writestr(item, data)
        if jc:
            zout.writestr("word/header1.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr {W_NS}><w:p>'
                          f'<w:pPr><w:jc w:val="{jc}"/></w:pPr>' + _field("PAGE", "1") + "</w:p></w:hdr>")
    pathlib.Path(dest).write_bytes(buf.getvalue())


def _field(instr, shown=""):
    """the runs of a Word field; Word computes it on opening (or F9)"""
    return (f'<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> {instr} '
            f'</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t xml:space="preserve">{shown}</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


# placeholders written into the LaTeX for pandoc, replaced in the Word XML afterwards
_MARK = {"RHMARKTOC": ("Contents", 'TOC \\o "1-3" \\h \\z \\u'),
         "RHMARKLOF": ("List of figures", 'TOC \\h \\z \\t "Image Caption,1"'),
         "RHMARKLOT": ("List of tables", 'TOC \\h \\z \\t "Table Caption,1"')}
_FRONT_END = "RHMARKFRONTEND"
_MAIN = "RHMARKMAINMATTER"
_BR = " RHMARKBR "                                                     # line break in a heading ("Chapter 3" / title)


def _paragraph_with(text):
    return r"<w:p(?:\s[^>]*)?>(?:(?!<w:p[\s>]).)*?" + text + r"(?:(?!<w:p[\s>]).)*?</w:p>"


def _paragraphs(xml):
    return re.findall(r"<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p\s*/>", xml, flags=re.S)


def _title_page(front, layout, page):
    """the front-matter paragraphs laid out as a title page"""
    paras = [p for p in _paragraphs(front) if re.search(r"<w:t[ >]", p)]
    width = int(round((210 - page.left_mm - page.right_mm) * 56.6929))
    out = []
    for i, p in enumerate(paras):
        gap = int(round((layout.gaps_mm[i] if i < len(layout.gaps_mm) else layout.gaps_mm[-1]) * 56.6929))
        ppr = f'<w:spacing w:before="{gap}" w:after="0"/><w:jc w:val="center"/>'
        if layout.bottom and i >= len(paras) - layout.bottom:
            ppr = ('<w:framePr w:w="%d" w:wrap="around" w:vAnchor="margin" w:hAnchor="margin" w:xAlign="center" '
                   'w:yAlign="bottom"/><w:spacing w:before="0" w:after="120"/><w:jc w:val="center"/>' % width)
        p = re.sub(r"<w:pPr>.*?</w:pPr>|<w:pPr\s*/>", "", p, flags=re.S)
        p = re.sub(r"^<w:p(\s[^>]*)?>", lambda m: m.group(0) + f"<w:pPr>{ppr}</w:pPr>", p)
        if i < len(layout.sizes_pt):
            sz = int(round(layout.sizes_pt[i] * 2))
            p = re.sub(r"<w:r>(?!<w:rPr>)", "<w:r><w:rPr></w:rPr>", p)
            p = re.sub(r"<w:rPr>(.*?)</w:rPr>", lambda m: "<w:rPr>" + re.sub(r"<w:sz(Cs)? [^>]*/>", "", m.group(1))
                       + f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>', p, flags=re.S)
        out.append(p)
    return "".join(out)


def _sections(s, title_page, roman):
    """no page number on the title page; roman numbers for the preliminary pages, arabic from the main matter"""
    i = s.rfind("<w:sectPr")
    if i == -1:
        return s
    j = s.find("</w:sectPr>", i) + len("</w:sectPr>")
    final = s[i:j]
    add = lambda sect, extra: re.sub(r"(<w:pgMar [^>]*/>)", lambda m: m.group(1) + extra, sect, count=1)
    m = re.search(_paragraph_with(_MAIN), s, flags=re.S) if roman else None
    if m:
        first = add(final, '<w:pgNumType w:fmt="lowerRoman" w:start="1"/>' + ("<w:titlePg/>" if title_page else ""))
        last = add(final, '<w:pgNumType w:fmt="decimal" w:start="1"/>')
        s = s[:i] + last + s[j:]
        s = s[:m.start()] + f"<w:p><w:pPr>{first}</w:pPr></w:p>" + s[m.end():]
    elif title_page:
        s = s[:i] + add(final, "<w:titlePg/>") + s[j:]
    return s


def _postprocess(docx, chapters, page=None, title_page=None, profile=None):
    """Word fields for the contents and the lists of figures and tables, the title page, page numbering, and a request
    to Word to update the fields when the document is opened"""
    page = page or PageSetup()
    path = pathlib.Path(docx)
    zin = zipfile.ZipFile(io.BytesIO(path.read_bytes())); buf = io.BytesIO()
    # header and footer references whose part pandoc did not carry over from a publisher's template make Word refuse
    # the file: keep only those that point to a header or footer
    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    hf_ids = set(re.findall(r'Id="([^"]+)"[^>]*Type="[^"]*/(?:header|footer)"', rels)
                 + re.findall(r'Type="[^"]*/(?:header|footer)"[^>]*Id="([^"]+)"', rels))
    brk = "<w:pageBreakBefore/>" if chapters else ""
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                s = data.decode("utf-8")
                s = re.sub(r'<w:(?:header|footer)Reference [^>]*r:id="([^"]+)"[^>]*/>',
                           lambda m: m.group(0) if m.group(1) in hf_ids else "", s)
                for mark, (title, instr) in _MARK.items():
                    s = re.sub(_paragraph_with(mark), lambda m, t=title, i=instr:
                               f'<w:p><w:pPr><w:pStyle w:val="TOCHeading"/>{brk}</w:pPr><w:r><w:t>{t}</w:t></w:r></w:p>'
                               f"<w:p>{_field(i, 'Right-click and choose Update Field.')}</w:p>", s, count=1, flags=re.S)
                m = re.search(_paragraph_with(_FRONT_END), s, flags=re.S)
                if m:
                    start = s.find("<w:body>") + len("<w:body>")
                    front = _title_page(s[start:m.start()], title_page or TitlePage(sizes_pt=(), gaps_mm=(8,), bottom=0, numbered=True), page)
                    s = s[:start] + front + s[m.end():]
                s = re.sub(r"\s*" + _BR.strip() + r"\s*", "</w:t><w:br/><w:t xml:space=\"preserve\">", s)
                s = re.sub(r"(<m:nor\s*/>)\s*<m:sty [^>]*/>", r"\1", s)   # math: normal text or a style, not both (schema)
                # the list of abbreviations is a list, not a results table: no rules, no header row
                m_ab = re.search(r"<w:t(?:\s[^>]*)?>Abbreviations</w:t>.*?</w:p>\s*(<w:tbl>.*?<w:tblPr>)", s, re.S)
                if m_ab:
                    pr_end = s.find("</w:tblPr>", m_ab.end(1))                   # schema order: borders before layout/look
                    k = min([x for x in (s.find(t, m_ab.end(1)) for t in ("<w:shd", "<w:tblLayout", "<w:tblCellMar", "<w:tblLook"))
                             if x != -1 and x < pr_end] + [pr_end])
                    s = s[:k] + ('<w:tblBorders><w:top w:val="nil"/><w:bottom w:val="nil"/><w:insideH w:val="nil"/>'
                                 '</w:tblBorders>') + s[k:]
                    end = s.find("</w:tbl>", k)
                    s = s[:k] + re.sub(r'w:firstRow="1"', 'w:firstRow="0"', s[k:end]) + s[end:]
                has_title = bool(m) and not (title_page and title_page.numbered) and title_page is not None
                s = _sections(s, has_title, roman=_MAIN in s)
                if profile is not None:
                    s = _apply_profile(s, profile)
                data = s.encode("utf-8")
            if item.filename == "[Content_Types].xml":                   # default types for the images pandoc embeds
                s = data.decode("utf-8")
                for ext, ctype in (("png", "image/png"), ("jpeg", "image/jpeg"), ("jpg", "image/jpeg"), ("gif", "image/gif")):
                    if any(n.lower().endswith("." + ext) for n in zin.namelist()) and f'Extension="{ext}"' not in s:
                        s = re.sub(r"(<Types[^>]*>)", r'\1<Default Extension="%s" ContentType="%s"/>' % (ext, ctype), s, count=1)
                data = s.encode("utf-8")
            if item.filename == "word/settings.xml":
                s = data.decode("utf-8")
                first = s.find("<w:proofState")                         # pandoc writes proofState twice
                if first != -1:
                    s = s[:first + 1] + re.sub(r"<w:proofState[^>]*/>", "", s[first + 1:])
                if "w:updateFields" not in s:
                    # schema order: ... updateFields, hdrShapeDefaults, footnotePr, endnotePr, compat, docVars, rsids, ...;
                    # pandoc writes footnotePr / endnotePr too early, so they are moved to their place as well
                    notes = "".join(re.findall(r"<w:(?:footnotePr|endnotePr)>.*?</w:(?:footnotePr|endnotePr)>", s, re.S))
                    s = re.sub(r"<w:(footnotePr|endnotePr)>.*?</w:\1>", "", s, flags=re.S)
                    later = ("<w:hdrShapeDefaults", "<w:compat", "<w:docVars", "<w:rsids", "<m:mathPr", "<w:attachedSchema",
                             "<w:themeFontLang", "<w:clrSchemeMapping", "<w:doNotIncludeSubdocsInStats", "<w:doNotAutoCompressPictures",
                             "<w:forceUpgrade", "<w:captions", "<w:readModeInkLockDown", "<w:smartTagType", "<sl:schemaLibrary",
                             "<w:shapeDefaults", "<w:doNotEmbedSmartTags", "<w:decimalSymbol", "<w:listSeparator")
                    hits = [x for x in (s.find(t) for t in later) if x != -1]
                    k = min(hits) if hits else s.rfind("</w:settings>")
                    hdr = re.search(r"<w:hdrShapeDefaults>.*?</w:hdrShapeDefaults>|<w:hdrShapeDefaults\s*/>", s[k:], re.S)
                    if hdr and hdr.start() == 0:                         # notes after hdrShapeDefaults
                        s = s[:k] + '<w:updateFields w:val="true"/>' + hdr.group(0) + notes + s[k + hdr.end():]
                    else:
                        s = s[:k] + '<w:updateFields w:val="true"/>' + notes + s[k:]
                data = s.encode("utf-8")
            zout.writestr(item, data)
    path.write_bytes(buf.getvalue())


_STYLE = re.compile(r"RHSTYLE([A-Za-z0-9]+)RHEND\s*")                 # paragraph style requested from the LaTeX side


def _png_for(name, dirs, png_dir):
    """Word cannot embed PDF: when a figure has only a PDF, render a 300 dpi PNG of it into png_dir"""
    if any((pathlib.Path(d) / f"{name}.png").exists() for d in dirs):
        return
    pdf = next((pathlib.Path(d) / f"{name}.pdf" for d in dirs if (pathlib.Path(d) / f"{name}.pdf").exists()), None)
    if pdf is None:
        return
    target = png_dir / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", str(pdf), str(target)], capture_output=True)
    else:
        try:
            import fitz                                                 # PyMuPDF, if installed
            fitz.open(pdf)[0].get_pixmap(dpi=300).save(str(target) + ".png")
        except Exception:
            print(f"figure {name}: only a PDF, and neither pdftoppm nor PyMuPDF is available to make a PNG")


def _front_block(pre, body, profile):
    """title block of a journal or conference paper as styled paragraphs: authors, affiliations, abstract and keywords
    (IEEEtran \\IEEEauthorblockN / \\IEEEauthorblockA, abstract, IEEEkeywords)"""
    def take(env):
        nonlocal body
        m = re.search(r"\\begin\{%s\}(.*?)\\end\{%s\}" % (env, env), body, re.S)
        if not m:
            return None
        body = body[:m.start()] + body[m.end():]
        return m.group(1).strip()
    abstract, keywords = take("abstract"), take("IEEEkeywords") or take("keywords")
    paras = []
    for text in (pre, body):
        m = re.search(r"\\author\s*\{", text)
        if not m:
            continue
        inner, end = _group(text, m.end() - 1)
        if text is body:
            body = body[:m.start()] + body[end:]
        inner = re.sub(r"\\thanks\{(?:[^{}]|\{[^{}]*\})*\}", "", inner or "")
        names = re.findall(r"\\IEEEauthorblockN\{((?:[^{}]|\{[^{}]*\})*)\}", inner)
        affs = re.findall(r"\\IEEEauthorblockA\{((?:[^{}]|\{[^{}]*\})*)\}", inner)
        if not names:
            names = [re.sub(r"\\and\b", ",", inner)]
        paras.append("RHSTYLEAuthorRHEND " + ", ".join(re.sub(r"\s*\\\\\s*", " ", n).strip() for n in names))
        for a in dict.fromkeys(affs):                                   # each affiliation once
            paras.append("RHSTYLEAffiliationRHEND " + re.sub(r"\s*\\\\\s*", r" \\\\ ", a.strip()))
        break
    if abstract:
        lab = f"\\textit{{{profile.abstract_label}}}---" if profile.abstract_label else ""
        paras.append(f"RHSTYLEAbstractRHEND {lab}{abstract}")
    if keywords:
        lab = f"\\textit{{{profile.keywords_label}}}---" if profile.keywords_label else ""
        paras.append(f"RHSTYLEKeywordsRHEND {lab}{keywords}")
    block = "\n\n" + "\n\n".join(paras) + "\n\n"
    return body.replace(r"\maketitle", block, 1) if r"\maketitle" in body else block + body


def _apply_profile(s, profile):
    """paragraph styles of the publisher's template, its numbering left to it, and the column layout"""
    def restyle(p, sid):
        p = re.sub(r'<w:pStyle w:val="[^"]*"\s*/>', "", p)
        if re.search(r"<w:pPr>", p):
            return p.replace("<w:pPr>", f'<w:pPr><w:pStyle w:val="{sid}"/>', 1)
        return re.sub(r"^(<w:p(?:\s[^>]*)?>)", lambda m: m.group(1) + f'<w:pPr><w:pStyle w:val="{sid}"/></w:pPr>', p)

    def para(p):
        m = _STYLE.search(p)
        if m:
            p = restyle(_STYLE.sub("", p, count=1), m.group(1))
        sid = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        if sid and sid.group(1) in profile.styles:
            p = restyle(p, profile.styles[sid.group(1)])
        if profile.strip_reference_numbers and f'<w:pStyle w:val="{profile.styles.get("Bibliography", "")}"' in p:
            p = re.sub(r"(<w:t(?:\s[^>]*)?>)\s*\[\d+\]\s*", r"\1", p, count=1)
            p = re.sub(r"<w:r>(?:<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?<w:tab/></w:r>", "", p, count=1, flags=re.S)
        return p
    s = re.sub(r"<w:p(?:\s[^>]*)?>.*?</w:p>", lambda m: para(m.group(0)), s, flags=re.S)
    if profile.columns > 1:
        i = s.rfind("<w:sectPr")
        j = s.find("</w:sectPr>", i) + len("</w:sectPr>")
        final = s[i:j]

        def cols(sect, n, cont):
            sect = re.sub(r"<w:cols\b[^>]*/>|<w:cols\b.*?</w:cols>|<w:type [^>]*/>", "", sect, flags=re.S)
            c = f'<w:cols w:num="{n}" w:space="{int(profile.column_space_pt * 20)}"/>' if n > 1 else "<w:cols/>"
            k = min([x for x in (sect.find("<w:titlePg"), sect.find("<w:docGrid"), sect.find("</w:sectPr>")) if x != -1])
            sect = sect[:k] + c + sect[k:]
            if cont:
                k = sect.find("<w:pgSz")
                sect = sect[:k] + '<w:type w:val="continuous"/>' + sect[k:]
            return sect
        # the columns start at the abstract (IEEE) or, without one, at the first heading
        first_heading = (re.search(r'<w:p(?:\s[^>]*)?>(?:(?!</w:p>).)*?<w:pStyle w:val="Abstract"', s, re.S)
                         or re.search(r'<w:p(?:\s[^>]*)?>(?:(?!</w:p>).)*?<w:pStyle w:val="Heading1"', s, re.S))
        if first_heading:
            k = first_heading.start()
            s = s[:i] + cols(final, profile.columns, True) + s[j:]
            s = s[:k] + f"<w:p><w:pPr>{cols(final, 1, False)}</w:pPr></w:p>" + s[k:]
    return s


def convert(main_tex, out_docx, csl=None, numbers=(), page=None, figure_width="15cm", front_matter="", keep_intermediate=False,
            title_page=None, reference_docx=None, profile=None):
    """Convert main_tex (and everything it inputs) to out_docx. Returns pandoc's exit code.
    front_matter: LaTeX for the first page (the title page of the PDF is not converted); title_page: a TitlePage to lay
    it out like a title page (otherwise its paragraphs are only centred); reference_docx: a publisher's Word template
    whose styles and page set-up are used instead of the generated ones (page is then ignored for styles); profile: a
    Profile (e.g. ieee_profile()) that also maps the styles, columns and numbering onto that template."""
    main_tex, out = pathlib.Path(main_tex).resolve(), pathlib.Path(out_docx).resolve()
    base, page = main_tex.parent, page or PageSetup()
    if profile is not None:
        reference_docx = profile.reference_docx
    src = main_tex.read_text(encoding="utf-8")
    pre, body = src.split(r"\begin{document}", 1)
    body = body.split(r"\end{document}", 1)[0]
    chapters = bool(re.search(r"\\documentclass(\[[^\]]*\])?\{(report|book|memoir|scrreprt|scrbook)\}", pre))
    abbr = _inline(pre, base)                                           # preamble inputs (abbreviations, macros)
    body = _inline(body, base)
    if profile is not None:
        body = _front_block(pre, body, profile)
    body = re.sub(r"\\IEEEPARstart\{([^}]*)\}\{([^}]*)\}", r"\1\2", body)
    body = re.sub(r"\\(IEEEoverridecommandlockouts|IEEEpeerreviewmaketitle|IEEEdisplaynontitleabstractindextext)\b", "", body)

    defs = "\n".join(pathlib.Path(f).read_text(encoding="utf-8") for f in numbers if pathlib.Path(f).exists()) + abbr
    body = _conditionals(body, defs)                                    # \IfName{a}{b} switched in the definitions
    body = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "", body, flags=re.S)
    body = re.sub(r"\\(begin|end)\{(frontmatter|graphicalabstract)\}", "", body)        # journal front matter (elsarticle)
    body = re.sub(r"\\begin\{highlights\}(.*?)\\end\{highlights\}",
                  lambda m: "\\section*{Highlights}\n\\begin{itemize}" + m.group(1) + "\\end{itemize}", body, flags=re.S)
    body = re.sub(r"\\begin\{keyword\}(.*?)\\end\{keyword\}",
                  lambda m: "\\textbf{Keywords:} " + m.group(1).replace("\\sep", ";"), body, flags=re.S)
    body = re.sub(r"\\(linenumbers|nolinenumbers)\b", "", body)
    if r"\pagenumbering{roman}" in body:                               # preliminary pages in roman numbers
        body = body.replace(r"\pagenumbering{arabic}", "\n\n" + _MAIN + "\n\n", 1)
    for macro, mark in (("tableofcontents", "RHMARKTOC"), ("listoffigures", "RHMARKLOF"), ("listoftables", "RHMARKLOT")):
        body = re.sub(r"\\" + macro + r"\b", "\n\n" + mark + "\n\n", body)
    body = re.sub(r"\\(tableofcontents|listoffigures|listoftables|clearpage|cleardoublepage|newpage|FloatBarrier|centering|glsaddall|onehalfspacing|doublespacing|maketitle)\b", "", body)
    body = re.sub(r"\\pagenumbering\{[^}]*\}|\\addcontentsline\{[^}]*\}\{[^}]*\}\{[^}]*\}|\\vspace\*?\{[^}]*\}|\\vfill|\\needspace\{[^}]*\}", "", body)
    acr = re.findall(r"\\newacronym(?:\[[^\]]*\])?\{[^}]*\}\{(.*?)\}\{(.*?)\}\s*$", abbr, re.M)
    if acr:
        rows = "\n".join(f"{s} & {l} \\\\" for s, l in acr)
        body = re.sub(r"\\printglossary(\[[^\]]*\])?|\\printacronyms(\[[^\]]*\])?",
                      lambda m: "\\section*{Abbreviations}\n\\begin{tabular}{ll}\n" + rows + "\n\\end{tabular}\n", body)
    body = _tables(body)
    body = re.sub(r"\\par\\smallskip\\parbox\{[^}]*\}\{\\footnotesize (.*?)\}\n", r"\n\\emph{Note.} \1\n", body)
    body = re.sub(r"\\setlist(\[[^\]]*\])?\{[^{}]*\}|\\raggedright\b|\\RaggedRight\b", "", body)
    body = re.sub(r"\\(tiny|scriptsize|footnotesize|small|normalsize)\b", "", body)
    body = re.sub(r"\\fbox\{\\parbox\{[^}]*\}\{(.*?)\}\}", r"\1", body, flags=re.S)
    text_cm = (210 - page.left_mm - page.right_mm) / 10
    col_cm = profile.column_width_cm if profile is not None and profile.column_width_cm else text_cm
    full_cm = profile.text_width_cm if profile is not None and profile.text_width_cm else text_cm
    figs = [base / "figures", base] + [base / p for p in re.findall(r"\{([^{}]+/)\}", (re.search(r"\\graphicspath\{(.*?)\}\s*$", pre, re.M) or [None, ""])[1])]
    png_dir = out.parent / f"_{out.stem}_png"

    def graphic(m):                                                     # the PDF's width, relative widths on the text block
        opts = m.group(1) or ""
        w = re.search(r"width\s*=\s*([\d.]*)\s*\\(linewidth|textwidth|columnwidth)", opts)
        u = re.search(r"width\s*=\s*([\d.]+\s*(?:cm|mm|in|pt))", opts)
        if w:
            width = f"{float(w.group(1) or 1) * (full_cm if w.group(2) == 'textwidth' else col_cm):.2f}cm"
        else:
            width = u.group(1).replace(" ", "") if u else figure_width
        name = re.sub(r"\.(pdf|png|jpe?g|eps)$", "", m.group(2))
        _png_for(name, figs, png_dir)
        return r"\includegraphics[width=" + width + "]{" + name + ".png}"
    body = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}", graphic, body)

    body = re.sub(r"\\label\[[^\]]*\]", lambda m: "\\label", body)          # cleveref \label[type]{key}
    body = re.sub(r"\\label\{([^}]+)\}", lambda m: "\\label{" + _bm(m.group(1)) + "}", body)
    body = re.sub(r"\\([cC]?ref|autoref)\{([^}]+)\}", lambda m: "\\" + m.group(1) + "{" + ",".join(_bm(k) for k in m.group(2).split(",")) + "}", body)
    body, names = _number(body, chapters, profile)

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
    if front_matter:
        front_matter = front_matter.rstrip() + "\n\n" + _FRONT_END + "\n\n"
    tex = "\\documentclass{article}\n\\begin{document}\n" + front_matter + body + "\n\\end{document}\n"
    tmp = out.with_suffix(".pandoc.tex"); tmp.write_text(tex, encoding="utf-8")
    bibs = []
    m = re.search(r"\\bibliography\{([^}]*)\}", src) or re.search(r"\\addbibresource\{([^}]*)\}", pre)
    for b in (m.group(1).split(",") if m else []):
        p = base / (b.strip() if b.strip().endswith(".bib") else b.strip() + ".bib")
        if p.exists():
            t = re.sub(r"(\btitle\s*=\s*)\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1{{\2}}", p.read_text(encoding="utf-8"))
            q = tmp_dir / f"_{p.stem}.bib"; q.write_text(t, encoding="utf-8"); bibs.append(q)
    ref = tmp_dir / "_reference.docx"; pandoc = pandoc_exe()
    if reference_docx:
        shutil.copy2(reference_docx, ref)
    else:
        reference_doc(ref, page, pandoc, chapters)
    cmd = [pandoc, str(tmp), "-f", "latex", "-t", "docx", "-o", str(out), "--resource-path", os.pathsep.join(str(f) for f in figs + [png_dir]),
           "--reference-doc", str(ref), "--metadata", f"lang={page.language}", "--metadata", "link-citations=true"]
    if title:
        cmd += ["--metadata", "title=" + re.sub(r"\\\\|\s+", " ", title.group(1)).strip()]
    if bibs:
        cmd += ["--citeproc"] + sum([["--bibliography", str(b)] for b in bibs], [])
    if csl:
        cmd += ["--csl", str(csl)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode == 0:
        _postprocess(out, chapters, page, title_page, profile)
    if not keep_intermediate:
        for f in [tmp, ref] + bibs:
            f.unlink(missing_ok=True)
        shutil.rmtree(png_dir, ignore_errors=True)
    missing = sorted(set(re.findall(r"\\hyperref\[([^\]]+)\]\{\1\}", body)))
    if r.returncode or missing:
        print(f"pandoc exit {r.returncode}; " + (r.stderr or "")[:1500])
    if missing:
        print("references without a target:", ", ".join(missing))
    return r.returncode
