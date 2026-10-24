"""A local library of paper templates and citation styles, fetched from their official sources, and new papers started
from them.

Command line:
    rh template list                         what is in the registry and what is already in the library
    rh template fetch [name ...]             download into the library (all downloadable entries if no name)
    rh template new <starter> <folder>       start a paper: main.tex, class and BibTeX style, references.bib, CSL, build notes

Python:
    from research_helpers import templates
    templates.fetch("ieeetran"); templates.new("ieee-conference", "papers/jurse2027")

The library lives in RH_TEMPLATES or ~/research-templates. Each entry is kept as downloaded (archives also unpacked)
with SOURCE.txt: address, date, SHA-256 and licence, so a template can be traced and refreshed. Nothing in the library
is overwritten: a newer download goes alongside, with the date in its folder name.

Some publishers only serve templates to a browser (IEEE's Word templates). Those entries are marked "manual": open the
address, save the files into the folder that `rh template list` shows, and they are used like the others.
"""
import datetime, hashlib, json, os, pathlib, shutil, urllib.request, zipfile

__all__ = ["REGISTRY", "STARTERS", "library", "fetch", "new", "status"]

CSL = "https://raw.githubusercontent.com/citation-style-language/styles/master/"
REGISTRY = {
    "ieeetran": {
        "urls": ["https://mirrors.ctan.org/macros/latex/contrib/IEEEtran.zip"],
        "licence": "LaTeX Project Public License 1.3",
        "about": "IEEEtran class and BibTeX styles, with bare_conf.tex (conferences) and bare_jrnl.tex (Transactions, "
                 "Letters) starters: IEEE conferences such as JURSE, and TGRS, JSTARS, GRSL"},
    "igarss-2026": {
        "urls": ["https://2026.ieeeigarss.org/Papers/PaperFormat/IGARSS2026LaTeXTemplate.zip",
                 "https://2026.ieeeigarss.org/Papers/PaperFormat/IG26_WordTemplate.zip",
                 "https://2026.ieeeigarss.org/Papers/PaperFormat/IG26_AbstractTemplate.docx"],
        "licence": "IEEE GRSS paper kit, for papers submitted to IGARSS",
        "about": "IGARSS 2026 paper kit: LaTeX and Word templates for 4-page full papers, Word template for abstracts. "
                 "Rules: https://2026.ieeeigarss.org/Papers/paper_kit.php"},
    "ec3-2026": {
        "urls": ["https://ec-3.org/wp-content/uploads/2026/04/2026_EC3_LaTex__FullPaper_Template.zip",
                 "https://ec-3.org/wp-content/uploads/2026/04/2026_EC3_Word__FullPaper_Template-.docx",
                 "https://ec-3.org/wp-content/uploads/2026/04/2026_GuideFullPaper_Template.pdf",
                 "https://ec-3.org/wp-content/uploads/2026/04/2026_EC3_LaTex__PosterExtendedAbstract_Template.zip",
                 "https://ec-3.org/wp-content/uploads/2026/04/2026_EC3_Word__PosterExtendedAbstract_Template-.docx",
                 "https://ec-3.org/wp-content/uploads/2026/04/2026_EC3_LaTex__PosterExtendedAbstract_Template.pdf"],
        "licence": "EC3 (European Council for Computing in Construction) author templates, for papers submitted to EC3",
        "about": "European Conference on Computing in Construction: full paper (8 pages, double-blind) and poster extended "
                 "abstract (2 pages, 800 words) templates, LaTeX and Word, with the author guide. "
                 "Rules: https://ec-3.org/conference/c2027/submissions/instructions-and-templates/"},
    "elsarticle": {
        "urls": ["https://mirrors.ctan.org/macros/latex/contrib/elsarticle.zip"],
        "post": ("elsarticle.ins", ["latex", "-interaction=nonstopmode", "elsarticle.ins"]),   # writes elsarticle.cls
        "licence": "LaTeX Project Public License 1.3",
        "about": "Elsevier journal class with Harvard and numbered templates (Remote Sensing of Environment, Energy and "
                 "Buildings, Sustainable Cities and Society, ...)"},
    "ieee-conference-word": {
        "manual": "https://www.ieee.org/conferences/publishing/templates.html",
        "licence": "IEEE conference template, free for use in IEEE conference papers",
        "about": "IEEE conference Word templates (A4 and US Letter) and the LaTeX bibliography files: the site only serves "
                 "them to a browser"},
    "ieee-transactions-word": {
        "manual": "https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/"
                  "tools-for-ieee-authors/ieee-article-templates/",
        "licence": "IEEE article templates, free for use in IEEE journal articles",
        "about": "IEEE Transactions and Letters Word and LaTeX templates (also on Overleaf): the site only serves them to "
                 "a browser"},
    "csl": {
        "urls": [CSL + n + ".csl" for n in ("ieee", "apa", "elsevier-harvard", "elsevier-with-titles", "harvard-cite-them-right",
                                             "multidisciplinary-digital-publishing-institute", "nature", "springer-basic-author-date")],
        "licence": "Creative Commons Attribution-ShareAlike 3.0 (Citation Style Language styles)",
        "about": "citation styles for pandoc and Zotero: IEEE, APA, Elsevier Harvard and numbered, Cite Them Right "
                 "Harvard, MDPI, Nature, Springer author-date"},
}

# starters: what `new` copies into a fresh paper folder. main: the template file (first match); files: (entry, pattern)
# pairs copied beside it; dirs: folders of the template copied as they are; bib: sample bibliography to start from
BUILD = "pdflatex main; bibtex main; pdflatex main; pdflatex main"
XEBUILD = "xelatex main; bibtex main; xelatex main; xelatex main"   # templates that load fontspec
STARTERS = {
    "ieee-conference": {"entry": "ieeetran", "main": ["bare_conf.tex"],
                        "files": [("ieeetran", "IEEEtran.cls"), ("ieeetran", "IEEEtran.bst")], "csl": "ieee.csl", "build": BUILD,
                        "about": "IEEE conference paper, two columns (JURSE, IEEE conferences in general)"},
    "ieee-journal": {"entry": "ieeetran", "main": ["bare_jrnl.tex"],
                     "files": [("ieeetran", "IEEEtran.cls"), ("ieeetran", "IEEEtran.bst")], "csl": "ieee.csl", "build": BUILD,
                     "about": "IEEE Transactions or Letters article (TGRS, JSTARS, GRSL)"},
    "igarss": {"entry": "igarss-2026", "main": ["IGARSS*LaTeXTemplate.tex", "*.tex"], "dirs": ["Figures"], "bib": "references.bib",
               "files": [("ieeetran", "IEEEtran.cls"), ("ieeetran", "IEEEtranN.bst")], "csl": "ieee.csl", "build": BUILD,
               "about": "IGARSS full paper, 4 pages, from the current paper kit (IEEEtran conference, A4)"},
    "ec3-paper": {"entry": "ec3-2026", "main": ["format_guide.tex"], "files": [("ec3-2026", "apalikenonitalic.bst"),
                  ("ec3-2026", "Extra.tex")], "dirs": ["img"], "bib": "references.bib", "csl": "apa.csl", "build": XEBUILD,
                  "about": "EC3 full paper, 8 pages including references, double-blind (European Conference on Computing in Construction)"},
    "ec3-poster": {"entry": "ec3-2026", "main": ["Poster.tex"], "files": [("ec3-2026", "apalikenonitalic.bst"),
                   ("ec3-2026", "Extra.tex")], "dirs": ["img"], "bib": "references.bib", "csl": "apa.csl", "build": XEBUILD,
                   "about": "EC3 poster extended abstract, 2 pages and at most 800 words"},
    "elsevier": {"entry": "elsarticle", "main": ["elsarticle-template-harv.tex", "elsarticle-template.tex"],
                 "files": [("elsarticle", "elsarticle.cls"), ("elsarticle", "elsarticle-harv.bst"), ("elsarticle", "elsarticle-num.bst")],
                 "csl": "elsevier-harvard.csl", "build": BUILD,
                 "about": "Elsevier journal article, Harvard citations (RSE, Energy and Buildings, ...)"},
}


def library(path=None):
    p = pathlib.Path(path or os.environ.get("RH_TEMPLATES") or pathlib.Path.home() / "research-templates")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _get(url, dest, tries=4):
    """download url to dest; mirrors.ctan.org sends each request to a random mirror, so a refusal is retried"""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research-helpers)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            if dest.suffix == ".zip" and not zipfile.is_zipfile(dest):
                raise RuntimeError(f"{url} did not return a zip archive (the site may only serve browsers)")
            return
        except Exception:
            dest.unlink(missing_ok=True)
            if i == tries - 1:
                raise


def fetch(names=None, lib=None, quiet=False):
    """download registry entries into the library; returns {name: folder}"""
    lib, out = library(lib), {}
    for name in names or [n for n, e in REGISTRY.items() if "urls" in e]:
        e = REGISTRY[name]
        if "urls" not in e:
            print(f"{name}: manual download from {e['manual']} into {lib / name}") if not quiet else None
            (lib / name).mkdir(exist_ok=True); out[name] = lib / name
            continue
        folder = lib / name
        if folder.exists() and any(folder.iterdir()):
            folder = lib / f"{name}_{datetime.date.today():%Y-%m-%d}"     # never overwrite: keep the earlier download
            if folder.exists():
                out[name] = folder; continue
        (folder / "download").mkdir(parents=True, exist_ok=True)
        rows = []
        try:
            for url in e["urls"]:
                _get(url, folder / "download" / url.rsplit("/", 1)[-1])
        except Exception as err:                                        # remove only what this call created
            shutil.rmtree(folder, ignore_errors=True)
            print(f"{name}: not downloaded ({err})")
            continue
        for url in e["urls"]:
            dest = folder / "download" / url.rsplit("/", 1)[-1]
            if dest.suffix == ".zip":
                with zipfile.ZipFile(dest) as z:
                    z.extractall(folder / "files" / dest.stem)
            else:
                (folder / "files").mkdir(exist_ok=True); shutil.copy2(dest, folder / "files" / dest.name)
            rows.append(f"{url}\n  sha256 {_sha(dest)}  {dest.stat().st_size:,} bytes")
        if e.get("post"):                                               # generate files the archive only has as source
            ins = next((folder / "files").rglob(e["post"][0]), None)
            if ins:
                import subprocess
                r = subprocess.run(e["post"][1], cwd=ins.parent, capture_output=True, text=True, errors="replace")
                rows.append(f"generated with `{' '.join(e['post'][1])}` in {ins.parent.relative_to(folder)} (exit {r.returncode})")
        (folder / "SOURCE.txt").write_text(f"{name}: {e['about']}\nLicence: {e['licence']}\nDownloaded {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n"
                                            + "\n".join(rows) + "\n", encoding="utf-8")
        out[name] = folder
        if not quiet:
            print(f"{name}: {len(e['urls'])} file(s) -> {folder}")
    return out


def _latest(lib, entry):
    cands = sorted([p for p in lib.glob(f"{entry}*") if p.is_dir() and (p.name == entry or p.name.startswith(entry + "_"))])
    return cands[-1] if cands else None


def _find(root, patterns):
    for pat in patterns:
        hits = sorted(p for p in root.rglob(pat) if "__MACOSX" not in p.parts and not p.name.startswith("._"))
        if hits:
            return hits
    return []


def new(starter, dest, lib=None):
    """start a paper in dest (which must be empty or new) from a starter template; returns the folder"""
    lib, s = library(lib), STARTERS[starter]
    src = _latest(lib, s["entry"]) or fetch([s["entry"]], lib)[s["entry"]]
    dest = pathlib.Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty: choose a new folder (nothing is overwritten)")
    dest.mkdir(parents=True, exist_ok=True)
    mains = _find(src, s["main"])
    if not mains:
        raise SystemExit(f"no {s['main']} in {src}")
    shutil.copy2(mains[0], dest / "main.tex")
    for entry, pat in s.get("files", []):
        root = src if entry == s["entry"] else (_latest(lib, entry) or fetch([entry], lib)[entry])
        hit = _find(root, [pat])
        if hit and not (dest / hit[0].name).exists():
            shutil.copy2(hit[0], dest / hit[0].name)
    for d in s.get("dirs", []):
        hit = sorted(p for p in src.rglob(d) if p.is_dir() and "__MACOSX" not in p.parts)
        if hit:
            shutil.copytree(hit[0], dest / d, ignore=shutil.ignore_patterns(".DS_Store", "._*"))
    sample = _find(mains[0].parent, [s["bib"]]) if s.get("bib") else []
    csl = _latest(lib, "csl") or fetch(["csl"], lib)["csl"]
    hit = _find(csl, [s["csl"]])
    if hit:
        shutil.copy2(hit[0], dest / hit[0].name)
    head = "% references: export from Zotero with Better BibTeX (keep updated), or rh bib references.bib key=DOI ...\n"
    body = sample[0].read_text(encoding="utf-8", errors="replace") if sample else ""
    (dest / "references.bib").write_text(head + body, encoding="utf-8")
    (dest / "README.md").write_text(
        f"# New paper ({starter})\n\n{s['about']}. Started {datetime.date.today():%Y-%m-%d} from `{src.name}` "
        f"(see SOURCE.txt in the template library, {lib}).\n\n"
        f"- Write in `main.tex`; references in `references.bib`.\n- PDF: `{s['build']}`\n"
        f"- Word, for co-authors: `rh latex2docx main.tex paper.docx --csl {s['csl']}`\n"
        "- Check the venue's current author instructions (page limit, paper size, anonymity) before submission.\n",
        encoding="utf-8")
    print(f"{starter}: {dest} ({', '.join(sorted(p.name for p in dest.iterdir()))})")
    return dest


def status(lib=None):
    lib = library(lib)
    rows = []
    for name, e in REGISTRY.items():
        have = _latest(lib, name)
        files = [p for p in have.rglob("*") if p.is_file()] if have else []
        rows.append({"name": name, "kind": "manual" if "manual" in e else "download", "in_library": bool(files),
                     "folder": str(have or lib / name), "about": e["about"]})
    return rows
