"""LaTeX to web: one LaTeX source becomes Markdown chapters and figure images for a site builder.

Every project describes itself in a `Project`: where its files are, which macros and boxes it defines, and how its pages
are named. Numbers come from the .aux file of a finished PDF build, so the web and the PDF agree.

    project = Project(root=..., aux=..., chapters=[Chapter("intro", path)], url="/course/", out=..., figures=...)
    build_figures(project)   # needs pdflatex and pdftocairo
    build_pages(project)     # needs pandoc
"""
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PANDOC_TO = ("markdown-smart-raw_tex-raw_attribute+tex_math_dollars-fenced_divs-bracketed_spans-native_divs-native_spans"
             "+pipe_tables+grid_tables-simple_tables-multiline_tables")
FIGURE = re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.S)
TIKZ = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.S)


@dataclass
class Chapter:
    slug: str
    path: Path
    group: str = ""


@dataclass
class Project:
    root: Path                      # folder LaTeX runs in
    aux: Path                       # .aux of a finished build
    chapters: list                  # Chapter items in reading order
    url: str                        # site path of the course, ending in /
    out: Path                       # where Markdown chapters go
    figures: Path                   # where figure images go
    preamble: list = field(default_factory=list)      # LaTeX lines before \begin{document} for the figure document
    macros: str = ""                # \newcommand lines pandoc needs
    boxes: dict = field(default_factory=dict)         # environment: (css class, default title)
    search: list = field(default_factory=list)        # folders searched for \input files
    inline_generated: tuple = ()    # generated files that hold text, inlined into the page
    definition_inputs: tuple = ()   # generated files that only define macros
    figure_macros: tuple = ()       # macros that draw a picture
    bibliography: Path = None
    csl: Path = None
    group_names: dict = field(default_factory=dict)
    index_head: list = field(default_factory=list)    # front matter and intro lines of the index page
    description: str = "{label}"
    dpi: int = 130
    job: str = "web_figs"
    to: str = ""                    # pandoc output format, when a site builder needs another


def read(path):
    return Path(path).read_bytes().decode("utf8").replace("\r\n", "\n")


def strip_comments(s):
    return re.sub(r"(?m)(?<!\\)%.*$", "", s)


CODE = re.compile(r"\\begin\{(lstlisting|verbatim)\}.*?\\end\{\1\}", re.S)
SHIELD = re.compile(r"SHIELD([0-9a-f]+)ENDS")


def protect(s):
    """Hide code blocks, whose text may look like LaTeX commands or comments, from the steps that follow."""
    return CODE.sub(lambda m: "SHIELD" + m[0].encode("utf8").hex() + "ENDS", s)


def unprotect(s):
    return SHIELD.sub(lambda m: bytes.fromhex(m[1]).decode("utf8"), s)


def load(path):
    return strip_comments(protect(read(path)))


def close_brace(s, i):
    """Index just past the brace group that opens at s[i]."""
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


def command_arg(s, cmd):
    """(start, end, argument) of the first \\cmd[..]{..}, or None."""
    m = re.search(r"\\" + cmd + r"\*?(\[[^\]]*\])?\s*\{", s)
    if not m:
        return None
    e = close_brace(s, m.end() - 1)
    return m.start(), e, s[m.end():e - 1]


def labels(aux):
    """label: printed number, from an .aux file."""
    return {m[1]: m[2] for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", read(aux).replace("\n", ""))}


def expand(s, project):
    """Inline every \\input that holds text; leave drawings and macro files in place."""
    def rep(m):
        name = m[1]
        if "#" in name or ("generated/" in name and not any(k in name for k in project.inline_generated)):
            return m[0]
        target = name if name.endswith(".tex") else name + ".tex"
        for base in [project.root, *project.search]:
            if (Path(base) / target).exists():
                return expand(load(Path(base) / target), project)
        return expand(load((Path(project.root) / target).resolve()), project)
    return re.sub(r"\\input\{([^}]+)\}", rep, s)


def macro_calls(s, name):
    out = []
    for m in re.finditer(r"\\" + name + r"\s*\{", s):
        e = close_brace(s, m.end() - 1)
        while s[e:e + 1] == "{":
            e = close_brace(s, e)
        out.append((m.start(), e))
    return out


def def_spans(s):
    """Where macro definitions sit in the text."""
    out = []
    for m in re.finditer(r"\\(?:newcommand|renewcommand|providecommand)\s*\{", s):
        e = close_brace(s, m.end() - 1)
        e += re.match(r"\s*(\[[^\]]*\])*\s*", s[e:]).end()
        if s[e:e + 1] == "{":
            out.append((m.start(), close_brace(s, e)))
    return out


def split_figures(s, project):
    """Replace figures and loose drawings with markers. Returns the text and a list of (latex, caption, label)."""
    items = []
    for a, b in reversed(def_spans(s)):
        s = s[:a] + s[b:]

    def marker():
        return f"\n\nFIGMARK{len(items) - 1}END\n\n"

    def figure(m):
        body, caption, label = m[1], "", ""
        if "\\caption" in body:
            i = body.rindex("\\caption")
            start = body.index("{", i)
            e = close_brace(body, start)
            caption = body[start + 1:e - 1]
            body = body[:i] + body[e:]
        found = re.search(r"\\label\{([^}]+)\}", caption) or re.findall(r"\\label\{([^}]+)\}\s*$", body)
        if found:
            label = found[1] if hasattr(found, "group") else found[-1]
        caption = re.sub(r"\\label\{[^}]+\}", "", caption)
        body = re.sub(r"\\label\{[^}]+\}", "", body)
        items.append((body, caption, label))
        return marker()

    def loose(m):
        items.append((m[0], "", ""))
        return marker()

    s = FIGURE.sub(figure, s)
    s = TIKZ.sub(loose, s)
    keep = "|".join(re.escape(k) for k in project.definition_inputs)
    s = re.sub(r"\\input\{generated/" + (f"(?!{keep})" if keep else "") + r"[^}#]+\}", loose, s)
    for name in project.figure_macros:
        for a, b in reversed(macro_calls(s, name)):
            items.append((s[a:b], "", ""))
            s = s[:a] + marker() + s[b:]
    return s, items


def top_defs(s, project):
    """Definitions at the top level of a chapter, which its figures need."""
    out = [s[a:b] for a, b in def_spans(s)]
    if project.definition_inputs:
        out += re.findall(r"\\input\{[^}]*(?:" + "|".join(re.escape(k) for k in project.definition_inputs) + r")[^}]*\}", s)
    return "\n".join(x.replace("\\newcommand", "\\providecommand") for x in out)


def build_figures(project):
    """Compile every figure as a page of one PDF, then render the pages to PNG. Returns (figures, pages, errors)."""
    lab = labels(project.aux)
    doc = [*project.preamble, r"\usepackage[active,tightpage]{preview}", r"\setlength\PreviewBorder{6pt}", 
           r"\begin{document}", r"\makeatletter"]
    for k, v in lab.items():
        if "@" not in k and "\\" not in k:
            doc.append(r"\expandafter\gdef\csname r@" + k + r"\endcsname{{" + v + "}{0}{}{}{}}")
    doc.append(r"\makeatother")
    count = 0
    for chapter in project.chapters:
        s = expand(load(chapter.path), project)
        doc.append(top_defs(FIGURE.sub("", s), project))
        for body, _, _ in split_figures(s, project)[1]:
            doc.append(r"\begin{preview}\begin{minipage}{\textwidth}\captionsetup{type=figure}\centering" + "\n" + body + "\n" + r"\end{minipage}\end{preview}")
            count += 1
    doc.append(r"\end{document}")
    root = Path(project.root)
    (root / f"{project.job}.tex").write_text("\n".join(doc), encoding="utf8", newline="\n")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", f"{project.job}.tex"], cwd=root, capture_output=True)
    log = (root / f"{project.job}.log").read_text(encoding="latin-1")
    found = re.search(r"Output written on .*?\((\d+) pages?", log)
    errors = re.findall(r"(?m)^! .*", log)
    pages = int(found[1]) if found else 0
    if pages:
        folder = Path(project.figures)
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            old.unlink()
        subprocess.run(["pdftocairo", "-png", "-r", str(project.dpi), str(root / f"{project.job}.pdf"), str(folder / "f")], check=True)
    return count, pages, errors


def token(label):
    return "XREF" + label.encode().hex() + "ENDX"


def to_markdown(tex, project, page_of, numbers):
    """LaTeX to Markdown through pandoc, with citations; cross-references become links."""
    pandoc = shutil.which("pandoc")
    args = [pandoc, "-f", "latex", "-t", project.to or PANDOC_TO, "--wrap=none"]
    if project.bibliography:
        args += ["--citeproc", f"--bibliography={project.bibliography}", "-M", "suppress-bibliography=true"] + ([f"--csl={project.csl}"] if project.csl else [])
    r = subprocess.run(args, input=(project.macros + unprotect(tex)).encode("utf8"), capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf8", "replace")[:800])

    def link(m):
        key = bytes.fromhex(m[1]).decode()
        n = numbers.get(key, "?")
        return f"[{n}]({project.url}{page_of[key]}/#{key})" if key in page_of else n
    return re.sub(r"XREF([0-9a-f]+)ENDX", link, r.stdout.decode("utf8").replace("\r\n", "\n"))


def prepare(s, chapter, numbers, project):
    """Rewrite chapter LaTeX into a form pandoc reads faithfully."""
    s = s.replace("\\thechapter", chapter)
    # a footnote giving a link's address is for printed copies; on the web the link itself is enough
    s = re.sub(r"(\\href\{[^{}]*\}\{(?:[^{}]|\{[^{}]*\})*\})\\footnote\{\\texttt\{[^{}]*\}\}", r"\1", s)
    s = re.sub(r"\\input\{[^}]*\}", "", s)

    def listing(m):
        q = (Path(project.root) / m[1]).resolve()
        return "\\begin{verbatim}\n" + read(q) + "\\end{verbatim}" if q.exists() else ""
    s = re.sub(r"\\lstinputlisting\{([^}]+)\}", listing, s)
    s = re.sub(r"\\begin\{(enumerate|itemize|description)\}\[(?:[^\[\]]|\[[^\]]*\])*\]", r"\\begin{\1}", s)
    s = re.sub(r"\\(begin|end)\{landscape\}", "", s)

    def where(m):
        rows = []
        for line in m[1].strip().split("\\\\"):
            cells = [x.strip() for x in line.split("&")]
            if len(cells) >= 2:
                cells[0] = f"${cells[0]}$"
                rows.append(" & ".join(cells + [""] * (3 - len(cells))) + " \\\\")
        return "\\textit{where}\n\n\\begin{tabular}{lll}\n" + "\n".join(rows) + "\n\\end{tabular}\n"
    s = re.sub(r"\\begin\{where\}(.*?)\\end\{where\}", where, s, flags=re.S)
    for env, (css, title) in project.boxes.items():
        def open_box(m, css=css, title=title):
            return f"\n\nBOXOPEN{css}BOXT {m[1] or title} BOXTEND\n\n"
        s = re.sub(r"\\begin\{" + env + r"\}(?:\[((?:[^\[\]]|\{[^}]*\})*)\])?", open_box, s)
        s = s.replace("\\end{" + env + "}", "\n\nBOXCLOSE\n\n")

    def eq_label(m):
        return "\\tag{" + numbers.get(m[1], "?") + "}"
    s = re.sub(r"(\\begin\{(equation|align)\}.*?\\end\{\2\})", lambda m: re.sub(r"\\label\{([^}]+)\}", eq_label, m[0]).replace("{equation}", "{equation*}").replace("{align}", "{align*}"), s, flags=re.S)

    def table_caption(m):
        return f"\\caption{{Table {numbers.get(m[2], '')}. {m[1]}}}"
    s = re.sub(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}\s*\\label\{([^}]*tab[^}]*)\}", table_caption, s)
    s = re.sub(r"\\eqref\{([^}]+)\}|\\xeqref\{([^}]+)\}", lambda m: "(" + token(m[1] or m[2]) + ")", s)
    s = re.sub(r"\\x?ref\{([^}]+)\}", lambda m: token(m[1]), s)
    count = [0, 0]

    def number(m):
        if m[1] == "section":
            count[0] += 1
            count[1] = 0
            return f"\\section{{{chapter}.{count[0]} "
        count[1] += 1
        return f"\\subsection{{{chapter}.{count[0]}.{count[1]} "
    return re.sub(r"\\(section|subsection)\{", number, s)


def units_out_of_text(md):
    """Move math macros out of \\text inside equations, whatever their nesting: browsers do not read them there."""
    i = 0
    pattern = re.compile(r"\\(text|textbf)\{")
    while True:
        m = pattern.search(md, i)
        if not m:
            return md
        e = close_brace(md, m.end() - 1)
        body = md[m.end():e - 1]
        if "\\ensuremath{" not in body:
            i = e
            continue
        a = body.index("\\ensuremath{")
        b = close_brace(body, a + len("\\ensuremath"))
        md = md[:m.start()] + f"\\{m[1]}{{{body[:a]}}}{body[a + len(chr(92) + 'ensuremath'):b]}\\{m[1]}{{{body[b:]}}}" + md[e:]
        i = m.start()


def finish(md):
    """Restore boxes and tidy equations in Markdown from pandoc."""
    def box(m):
        t = re.sub(r"\\ensuremath\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", m[2])
        t = re.sub(r"\$\^\{\\circ\}\\mathrm\{C\}\$", "\u00b0C", t)
        t = re.sub(r"\$([^$]*)\$", r"\\(\1\\)", t).replace("**", "")
        return f'<div class="box box-{m[1]}" markdown="1"><p class="box-title">{t}</p>\n'
    md = re.sub(r"BOXOPEN(\w+?)BOXT (.*?)\s*BOXTEND", box, md, flags=re.S)
    md = md.replace("\\begin{equation*}", "").replace("\\end{equation*}", "")
    inner = r"((?:[^{}]|\{[^{}]*\})*?)"
    for _ in range(6):
        md = re.sub(r"\\(text|textbf)\{" + inner + r"\\ensuremath\{((?:[^{}]|\{[^{}]*\})*)\}", lambda m: "\\" + m[1] + "{" + m[2].replace("\\,", " ") + "}" + m[3] + "\\" + m[1] + "{", md)
    md = re.sub(r"\\(text|textbf)\{([^{}]*)\}", lambda m: "\\" + m[1] + "{" + m[2].replace("\\,", " ") + "}", md)
    md = md.replace("BOXCLOSE", "</div>")
    md = re.sub(r"(?m)^(#+) ", r"#\1 ", md)
    return units_out_of_text(md).replace('<div id="refs"', '## References\n\n<div id="refs"')


def build_pages(project):
    """Write one Markdown file per chapter and an index page. Returns (chapters, figures used)."""
    numbers = labels(project.aux)
    page_of, texts = {}, {}
    for chapter in project.chapters:
        s = expand(load(chapter.path), project)
        for key in re.findall(r"\\label\{([^}]+)\}", s):
            page_of[key] = chapter.slug
        texts[chapter.slug] = s
    out = Path(project.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("[0-9]*.md"):
        old.unlink()
    width = len(str(sum(1 for _ in Path(project.figures).glob("*.png"))))
    index, group, figure_no = list(project.index_head), None, 1
    for i, chapter in enumerate(project.chapters, 1):
        s = texts[chapter.slug]
        m = command_arg(s, "chapter")
        title = re.sub(r"\\[a-zA-Z]+\s*", "", m[2]) if m else chapter.slug
        found = re.search(r"\\label\{([^}]+)\}", s[m[0]:m[1] + 80]) if m else None
        number = numbers.get(found[1], str(i)) if found else str(i)
        s = s[m[1]:] if m else s
        s = re.sub(r"\A\s*(\\label\{[^}]+\}\s*)+", "", s)
        s, items = split_figures(s, project)
        md = to_markdown(prepare(s, number, numbers, project), project, page_of, numbers)
        for n, (_, caption, label) in enumerate(items):
            text = to_markdown(prepare(caption, number, numbers, project), project, page_of, numbers).strip().replace("\n", " ") if caption else ""
            # alt text from the rendered caption: link text kept, link targets and Markdown marks dropped
            alt = re.sub(r"\s+", " ", re.sub(r"[`*_\[\]<>\\$]", "", re.sub(r"\]\([^)]*\)", "]", text)))[:200].strip() or "Figure"
            head = f"**Figure {numbers.get(label, '')}.** " if label else ""
            anchor = f'<a id="{label}"></a>\n\n' if label else ""
            md = md.replace(f"FIGMARK{n}END", f"{anchor}![{alt}]({project.url}fig/f-{str(figure_no + n).zfill(width)}.png)\n\n{head}{text}")
        figure_no += len(items)
        md = finish(md)
        title = title.replace("--", "\u2013")
        name = f"{number}. {title}" if number.isdigit() or len(number) == 1 else title
        if chapter.group != group and chapter.group:
            index.append(f"\n**{project.group_names.get(chapter.group, chapter.group)}**\n")
            group = chapter.group
        index.append(f"- [{name}]({chapter.slug}/)")
        (out / f"{i:02d}-{chapter.slug}.md").write_text(f'---\ntitle: "{name}"\nslug: {chapter.slug}\ndescription: {project.description.format(label=name)}\n---\n\n{md}\n', encoding="utf8", newline="\n")
    (out / "00-index.md").write_text("\n".join(index) + "\n", encoding="utf8", newline="\n")
    return len(project.chapters), figure_no - 1
