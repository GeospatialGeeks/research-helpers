"""One way to build documents and sites from LaTeX, on top of latexmk, Pandoc and Zensical.

A project holds a document.toml. Everything else is shared:

    python -m research_helpers.stack layouts
    python -m research_helpers.stack pdf  <project> [layout ...]     PDFs, one per layout
    python -m research_helpers.stack web  <project>                  chapters, one long page, embedded PDF, through Zensical
    python -m research_helpers.stack check <project>                 names, and things a build depends on
    python -m research_helpers.stack snapshot <project>              pictures of each output, kept with dates

Example document.toml:

    name = "sar_reading_manual"
    title = "Reading radar images"
    subtitle = "A working manual"
    author = "Ahmad Ammar"
    layouts = ["manual"]
    source = "tex"
    chapters = ["ch_science", "ch_basics"]
    figures = "figures"
    [web]
    site_name = "Reading radar images"
    pdf_name = "Reading_radar_images_Ahmad_Ammar.pdf"
"""
import datetime
import functools
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
LATEX = HERE / "latex"
TEMPLATES = Path(os.environ.get("RH_TEMPLATES", Path.home() / "research-templates"))

PACKAGES = r"\usepackage[T1]{fontenc}" + "\n" + r"\usepackage{lmodern,xurl}" + "\n"
BOOK = PACKAGES + "\\usepackage[margin=24mm]{geometry}\n\\usepackage{rhcommon}\n\\usepackage[authoryear,round]{natbib}\n"
PAPER = PACKAGES + "\\usepackage{amsmath,amssymb,booktabs,graphicx,float,listings,tabularx}\n\\usepackage[hidelinks]{hyperref}\n\\newcommand{\\snippetcaption}[1]{\\texttt{#1}}\n"
ARTICLE_TOKENS = "\\usepackage[margin=25mm]{geometry}\n\\usepackage{rhcommon}\n\\usepackage[authoryear,round]{natbib}\n"


def _authors_elsevier(d):
    out, seen = [], {}
    for a in d.get("authors", [dict(name=d.get("author", ""))]):
        k = a.get("affiliation", "")
        seen.setdefault(k, f"a{len(seen) + 1}")
        out.append(f"\\author[{seen[k]}]{{{a['name']}{chr(92) + 'corref{cor}' if a.get('corresponding') else ''}}}" + (f"\n\\ead{{{a['email']}}}" if a.get("email") else ""))
    out.append("\\cortext[cor]{Corresponding author.}")
    out += [f"\\affiliation[{v}]{{organization={{{k}}}}}" for k, v in seen.items() if k]
    return "\n".join(out)


def _authors_ieee(d):
    return "\\author{" + "\\and ".join(f"\\IEEEauthorblockN{{{a['name']}}}\\IEEEauthorblockA{{{a.get('affiliation', '')}}}" for a in d.get("authors", [dict(name=d.get("author", ""))])) + "}"


def _elsevier(options, d):
    keys = " \\sep ".join(d.get("keywords", []))
    return f"""\\documentclass[{options}]{{elsarticle}}
{PAPER}{d['_extra']}\\journal{{{d.get('journal', 'Journal')}}}
\\begin{{document}}
\\begin{{frontmatter}}
\\title{{{d['title']}}}
{_authors_elsevier(d)}
\\begin{{abstract}}
\\input{{{d.get('abstract', 'abstract')}}}
\\end{{abstract}}
\\begin{{keyword}}
{keys}
\\end{{keyword}}
\\end{{frontmatter}}
{d['_body']}
{d['_bib']('elsarticle-harv')}
\\end{{document}}
"""


def _ieee(d):
    keys = ", ".join(d.get("keywords", []))
    return f"""\\documentclass[conference]{{IEEEtran}}
{PAPER}\\usepackage[numbers,sort&compress]{{natbib}}
{d['_extra']}\\begin{{document}}
\\title{{{d['title']}}}
{_authors_ieee(d)}
\\maketitle
\\begin{{abstract}}
\\input{{{d.get('abstract', 'abstract')}}}
\\end{{abstract}}
\\begin{{IEEEkeywords}}
{keys}
\\end{{IEEEkeywords}}
{d['_body']}
{d['_bib']('IEEEtranN')}
\\end{{document}}
"""


def _book(style, klass="report"):
    def make(d):
        toc = "\\tableofcontents\n" if d.get("contents", True) else ""
        date = d.get("date", datetime.date.today().strftime("%d %B %Y").lstrip("0"))
        return f"""\\documentclass[11pt,a4paper]{{{klass}}}
{BOOK}{d['_extra']}\\graphicspath{{{d['_graphics']}}}
\\begin{{document}}
\\rhtitle{style}{{{d['title']}}}{{{d.get('subtitle', '')}}}{{{d.get('author', '')}}}{{{date}}}
{toc}{d['_body']}
{d['_bib']('agsm')}
\\end{{document}}
"""
    return make


LAYOUTS = {
    "elsevier": (lambda d: _elsevier("preprint,12pt,authoryear", d), "Journal review copy, single column", ["elsarticle"]),
    "elsevier-print": (lambda d: _elsevier("final,5p,times,twocolumn,authoryear", d), "Two columns, as it would look in print", ["elsarticle"]),
    "ieee": (_ieee, "IEEE conference, two columns, numbered citations", ["ieeetran"]),
    "manual": (_book("manual"), "Guide, tutorial or documentation", []),
    "pamphlet": (_book("pamphlet", "article"), "Long essay with a centred title page", []),
    "report": (_book("plain", "article"), "Working record, with a compact title", []),
    "own": (None, "The project's own main file, for a required template such as a thesis class", []),
}


def load(project):
    project = Path(project).resolve()
    d = tomllib.loads((project / "document.toml").read_text(encoding="utf8"))
    d["_root"] = project
    d["_src"] = project / d.get("source", "paper")
    return d


def tokens():
    return tomllib.loads((HERE / "tokens.toml").read_text(encoding="utf8"))


def write_tokens(folder):
    t = tokens()
    c, s, ty = t["colour"], t["spacing"], t["type"]
    lines = [f"\\definecolor{{rh{k.replace('_', '')}}}{{HTML}}{{{v}}}" for k, v in c.items()]
    lines += [f"\\newcommand{{\\rh{k.replace('_', '')}}}{{{v}}}" for k, v in s.items()]
    lines.append(f"\\newcommand{{\\rhcodesize}}{{\\{ty['code_size_pdf']}}}")
    (Path(folder) / "rhtokens.tex").write_text("\n".join(lines) + "\n", encoding="utf8")


def _template_files(names, dest):
    for name in names:
        latest = sorted((TEMPLATES / name / "files").glob("*")) if (TEMPLATES / name / "files").exists() else []
        roots = latest or [TEMPLATES / name]
        for f in Path(roots[-1]).rglob("*"):
            if f.suffix in (".cls", ".bst", ".sty") and f.is_file():
                shutil.copy2(f, dest / f.name)


def pdf(project, *wanted):
    """Write a thin wrapper for each layout and compile it. The project's own files are only read."""
    d = load(project)
    results = {}
    for name in wanted or d.get("layouts", ["manual"]):
        make, _, templates = LAYOUTS[name]
        out = d["_root"] / "build" / name
        out.mkdir(parents=True, exist_ok=True)
        if name == "own":
            results[name] = _own(d, out)
            print(name, results[name], flush=True)
            continue
        write_tokens(out)
        shutil.copy2(LATEX / "rhcommon.sty", out)
        _template_files(templates, out)
        fig = (d["_root"] / d.get("figures", "figures")).as_posix()
        d["_graphics"] = "{" + fig + "/}"
        extra = [f"\\graphicspath{{{d['_graphics']}}}"]
        src = d["_src"]
        extra += [f"\\input{{{v}}}" for v in d.get("defines", [])]
        d["_extra"] = "\n".join(extra) + "\n"
        parts = d.get("chapters") if name == "manual" and d.get("chapters") else [d["body"]] if d.get("body") else d.get("chapters", ["body"])
        d["_body"] = "\n".join(f"\\input{{{c}}}" for c in parts)
        bibfile = d.get("bibliography")
        if bibfile:
            shutil.copy2(src / bibfile, out / bibfile)
            d["_bib"] = lambda style, b=bibfile: f"\\bibliographystyle{{{style}}}\n\\bibliography{{{Path(b).stem}}}"
        else:
            d["_bib"] = lambda style: ""
        (out / "main.tex").write_text(make(d), encoding="utf8")
        env = dict(os.environ, TEXINPUTS=os.pathsep.join([str(out), str(src), ""]))
        run = lambda *c: subprocess.run(c, cwd=out, capture_output=True, env=env)
        for _ in range(2):
            run("pdflatex", "-interaction=nonstopmode", "main.tex")
        if bibfile:
            run("bibtex", "main")
            run("pdflatex", "-interaction=nonstopmode", "main.tex")
        run("pdflatex", "-interaction=nonstopmode", "main.tex")
        log = (out / "main.log").read_text(encoding="latin1", errors="replace")
        errors = sorted(set(re.findall(r"^! .*", log, re.M)))[:6]
        final = d["_root"] / "build" / f"{d['name']}_{name}.pdf"
        if (out / "main.pdf").exists():
            shutil.copy2(out / "main.pdf", final)
        results[name] = dict(pdf=str(final), errors=errors, undefined=sorted(set(re.findall(r"(?:Citation|Reference) [`']([^']+)'[^\n]*undefined", log)))[:6])
        print(name, results[name], flush=True)
    return results


def _own(d, out):
    """Compile the project's own driver, leaving its files in place and its by-products in build/own."""
    main = d.get("main", "main.tex")
    subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", f"-outdir={out}", main], cwd=d["_src"], capture_output=True)
    made = out / (Path(main).stem + ".pdf")
    final = d["_root"] / "build" / f"{d['name']}_own.pdf"
    if made.exists():
        shutil.copy2(made, final)
    log = out / (Path(main).stem + ".log")
    errors = sorted(set(re.findall(r"^! .*", log.read_text(encoding="latin1", errors="replace"), re.M)))[:6] if log.exists() else ["no log"]
    return dict(pdf=str(final) if made.exists() else None, errors=errors, undefined=[])


def web(project, source_pdf=None, build=True):
    """Chapters, one long page and an embedded PDF, as a Zensical site in build/site."""
    from .. import tex_web as T
    d = load(project)
    w = d.get("web", {})
    root, src = d["_root"], d["_src"]
    aux_dir = root / "build" / d["layouts"][0]
    docs = root / "build/site_src"
    if docs.exists():
        shutil.rmtree(docs)
    (docs / "fig").mkdir(parents=True)
    defines = d.get("defines", [])
    macros = "".join((src / (m if m.endswith(".tex") else m + ".tex")).read_text(encoding="utf8") + "\n" for m in defines) + "\\newcommand{\\snippetcaption}[1]{\\textbf{From the code:} \\texttt{#1}}\n"
    project_web = T.Project(
        root=src, aux=aux_dir / "main.aux", url="/", out=docs, figures=docs / "fig",
        chapters=[T.Chapter(c.replace("_", "-"), src / f"{c}.tex") for c in d["chapters"]],
        preamble=["\\documentclass[11pt,a4paper]{article}", "\\usepackage[T1]{fontenc}", "\\usepackage{lmodern,caption,amsmath,graphicx,booktabs,xcolor,listings,float,tabularx}", "\\usepackage[margin=24mm]{geometry}", f"\\graphicspath{{{{{(root / d.get('figures', 'figures')).as_posix()}/}}}}", *[f"\\input{{{m}}}" for m in defines], "\\newcommand{\\snippetcaption}[1]{\\textbf{From the code:} \\texttt{#1}}"],
        macros=macros, search=[src], definition_inputs=tuple(Path(m).name for m in defines), inline_generated=tuple(w.get("inline", ["snip_", "table_"])),
        description="{label}: " + d["title"], index_head=["---", f"title: {d['title']}", "slug: index", "---", "", w.get("intro", d.get("subtitle", "")), ""],
    )
    print("figures", T.build_figures(project_web), flush=True)
    T.build_pages(project_web)
    return _site(d, docs, build)


def _front(text):
    return text.split("---\n", 2)[2] if text.startswith("---") else text


def _clean(text):
    """What Zensical needs: display maths on its own lines, and links and pictures relative to the site."""
    text = re.sub(r"\s*\$\$(.+?)\$\$\s*", lambda m: "\n\n$$\n" + m[1].strip() + "\n$$\n\n", text, flags=re.S)
    text = re.sub(r"\]\(/fig/", "](fig/", text)
    text = re.sub(r"\]\(/([a-z0-9-]+)/#", r"](\1.md#", text)
    return re.sub(r"\]\(/([a-z0-9-]+)/\)", r"](\1.md)", text)


def _site(d, docs, build):
    root, w = d["_root"], d.get("web", {})
    nav, whole = [], []
    pages = sorted(docs.glob("[0-9]*.md"))
    index = docs / "00-index.md"
    for p in pages:
        raw = p.read_text(encoding="utf8")
        head = dict(x.split(": ", 1) for x in raw.split("---\n")[1].strip().splitlines() if ": " in x)
        title = head["title"].strip('"')
        body = _clean(_front(raw))
        slug = head["slug"]
        p.unlink()
        if slug == "index":
            (docs / "index.md").write_text(f"# {d['title']}\n\n{body}\n\n- [The whole guide on one page](full.md)\n- [Read or download the PDF](pdf.md)\n", encoding="utf8")
            continue
        (docs / f"{slug}.md").write_text(f"# {title}\n\n{body}", encoding="utf8")
        nav.append((title, f"{slug}.md"))
        whole.append(f"# {title}\n\n{re.sub(r'(?m)^(#+) ', lambda m: m[1] + '# ', body)}")
    (docs / "full.md").write_text("\n\n".join(whole), encoding="utf8")
    pdf_name = w.get("pdf_name", f"{d['name']}.pdf")
    made = root / "build" / f"{d['name']}_{d['layouts'][0]}.pdf"
    if made.exists():
        shutil.copy2(made, docs / pdf_name)
    (docs / "pdf.md").write_text(f"# Read or download the PDF\n\n[Download the PDF]({pdf_name})\n\n<div id=\"rh-pdf\" class=\"rh-pdf\" data-src=\"../{pdf_name}\"></div>\n", encoding="utf8")
    t = tokens()
    s = t["spacing"]
    css = ":root{" + "".join(f"--rh-{k.replace('_', '-')}:{v};" for k, v in s.items()) + f"--rh-body:{t['type']['body_web']}" + "}\n" + (HERE / "site.css").read_text(encoding="utf8").replace("TOKEN_ACCENT_DARK", t["colour"]["accent_dark"]).replace("TOKEN_ACCENT", t["colour"]["accent"])
    (docs / "rh.css").write_text(css, encoding="utf8")
    (docs / "mathjax.js").write_text('window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]],displayMath:[["\\\\[","\\\\]"]]},options:{ignoreHtmlClass:".*|",processHtmlClass:"arithmatex"}};document$&&document$.subscribe(()=>{if(window.MathJax&&MathJax.typesetPromise){MathJax.typesetClear&&MathJax.typesetClear();MathJax.typesetPromise()}});\n', encoding="utf8")
    shutil.copy2(HERE / "pdfview.js", docs / "pdfview.js")
    entries = "\n".join(f"  - {json_str(a)}: {b}" for a, b in [("Home", "index.md"), *nav, ("Whole guide", "full.md"), ("PDF", "pdf.md")])
    (root / "build/mkdocs.yml").write_text(f"""site_name: {json_str(w.get('site_name', d['title']))}
docs_dir: site_src
site_dir: site
theme:
  name: material
  features: [navigation.instant, navigation.top, navigation.footer, toc.follow, search.highlight]
  palette:
    - scheme: default
      toggle: {{icon: material/weather-night, name: Dark}}
    - scheme: slate
      toggle: {{icon: material/weather-sunny, name: Light}}
extra_css: [rh.css]
extra_javascript:
  - mathjax.js
  - pdfview.js
  - https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js
markdown_extensions:
  - attr_list
  - md_in_html
  - tables
  - toc: {{permalink: true}}
  - pymdownx.superfences
  - pymdownx.arithmatex: {{generic: true}}
nav:
{entries}
""", encoding="utf8")
    if build:
        exe = os.environ.get("RH_ZENSICAL") or shutil.which("zensical") or str(Path(sys.prefix) / "Scripts" / "zensical.exe")
        r = subprocess.run([exe, "build", "--clean"], cwd=root / "build", capture_output=True, text=True, encoding="utf8", errors="replace")
        print("zensical exit code", r.returncode, flush=True)
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)
    return root / "build/site"


def json_str(s):
    return '"' + str(s).replace('"', '\\"') + '"'


NAME_RULES = [("figures", r"^(map|fig|story)_[a-z0-9_]+(\.map)?\.(png|pdf|svg|json|pptx)$|^story_[a-z0-9_]+_(full|map)\.png$"), ("code", r"^(\d\d_)?[a-z0-9_]+\.(py|sh|js|R|csv|md)$"), ("src", r"^(\d\d_)?[a-z0-9_]+\.(py|sh|js|R)$")]


def check(project):
    """Report names that break the rules, and files the document needs but lacks. Changes nothing."""
    d = load(project)
    problems = []
    for folder, rule in NAME_RULES:
        for f in (d["_root"] / folder).glob("*") if (d["_root"] / folder).exists() else []:
            if f.is_file() and not re.match(rule, f.name):
                problems.append(f"name: {folder}/{f.name}")
    for c in [*d.get("chapters", []), *([d["body"]] if d.get("body") else [])]:
        if not (d["_src"] / f"{c}.tex").exists():
            problems.append(f"missing: {c}.tex")
    for v in re.findall(r"_v\d+\b|\bfinal\b", " ".join(p.name for p in d["_root"].rglob("*.tex") if "build" not in p.parts)):
        problems.append(f"iteration in a file name: {v}")
    print(d["name"], "problems", len(problems))
    for p in problems[:40]:
        print(" ", p)
    return problems


def layouts():
    for k, (_, about, _t) in LAYOUTS.items():
        print(f"{k:16} {about}")


def _browser():
    for b in ("msedge", "chrome", "chromium", "google-chrome", r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"):
        found = shutil.which(b)
        if found:
            return found


def _shoot_site(site, out, stem):
    """Pictures of the built site at desktop and phone width, through a local server."""
    browser = _browser()
    if not browser or not site.exists():
        return
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    pages = ["", "full/", "pdf/"] + sorted(f"{x.name}/" for x in site.glob("ch-*"))[:1]
    for page in pages:
        for label, size in (("desktop", "1300,1000"), ("phone", "500,900")):
            name = (page.strip("/") or "home") + "_" + label
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--virtual-time-budget=30000", f"--window-size={size}", f"--screenshot={out / f'{stem}_web_{name}.png'}", f"http://127.0.0.1:{server.server_port}/{page}"], capture_output=True)
    server.shutdown()


def snapshot(project, pages=2):
    """Keep dated pictures of what each build produced in snapshots/<date>, with a page to look through them."""
    d = load(project)
    day = datetime.date.today().isoformat()
    out = d["_root"] / "snapshots" / day
    out.mkdir(parents=True, exist_ok=True)
    for pdf_file in (d["_root"] / "build").glob(f"{d['name']}_*.pdf"):
        subprocess.run(["pdftoppm", "-r", "60", "-f", "1", "-l", str(pages), "-png", str(pdf_file), str(out / pdf_file.stem)], check=False)
    _shoot_site(d["_root"] / "build/site", out, d["name"])
    cards = "".join(f'<figure><a href="{f.name}"><img src="{f.name}" loading="lazy"></a><figcaption>{f.stem}</figcaption></figure>' for f in sorted(out.glob("*.png")))
    (out / "index.html").write_text(f'<!doctype html><meta charset="utf-8"><title>{d["name"]} {day}</title><style>body{{font:14px sans-serif;margin:16px}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}img{{width:100%;border:1px solid #ccc}}figcaption{{overflow-wrap:anywhere}}</style><h1>{d["name"]}, {day}</h1><main>{cards}</main>', encoding="utf8")
    print(out, len(list(out.glob("*.png"))), "pictures", flush=True)
    return out
