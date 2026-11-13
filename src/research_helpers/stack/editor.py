"""Editing a stack document from its LaTeX source, the same way in every project.

    python -m research_helpers.stack editor <repo>          # write .vscode settings and tasks once per repository
    python -m research_helpers.stack preview <file.tex>     # PDF of the document holding this file
    python -m research_helpers.stack preview <file.tex> web # its web pages as well

`preview` walks up from the file to the nearest document.toml, so it works for any chapter of any
document (guide, essay, pamphlet, book) without settings. The PDF is copied to
<document>/build/preview/<file>.pdf, where the VS Code PDF tab (LaTeX Workshop) looks for it.
A repository may name its own web command in a file `.stack-web` at its root (for example
`python build_guides.py {name}`), which `preview ... web` runs instead of stack.web.
"""
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def find_document(path):
    path = Path(path).resolve()
    return next((p for p in [path, *path.parents] if (p / "document.toml").exists()), None)


def preview(tex, *what):
    from . import pdf, web
    tex = Path(tex).resolve()
    doc = find_document(tex)
    if doc is None:
        sys.exit(f"no document.toml above {tex}")
    if "web" in what:
        repo = next((p for p in doc.parents if (p / ".git").exists()), None)
        own = repo / ".stack-web" if repo else None
        if own and own.exists():
            cmd = own.read_text(encoding="utf8").strip().format(name=doc.name, path=doc)
            sys.exit(subprocess.run(shlex.split(cmd.replace("python ", f'"{sys.executable}" ', 1), posix=False), cwd=repo).returncode)
        web(doc)
        return
    made = next((Path(r["pdf"]) for r in pdf(doc).values() if r and r.get("pdf")), None)
    if made is None:
        sys.exit("PDF not made; see the log in build/")
    out = doc / "build" / "preview"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(made, out / (tex.stem + ".pdf"))
    print("preview", out / (tex.stem + ".pdf"), flush=True)


def editor(repo="."):
    """Write VS Code settings so that saving any .tex file under a document.toml previews its PDF beside it,
    and Ctrl+Shift+B does the same (with a second task for the web pages). Existing keys are kept."""
    repo = Path(repo).resolve()
    vs = repo / ".vscode"
    vs.mkdir(exist_ok=True)
    py = Path(sys.executable).as_posix()
    run = [py, "-m", "research_helpers.stack", "preview"]
    settings = {
        "latex-workshop.latex.recipes": [{"name": "stack preview", "tools": ["stack-preview"]}],
        "latex-workshop.latex.tools": [{"name": "stack-preview", "command": py,
                                        "args": run[1:] + ["%DOC_EXT%"], "env": {"PYTHONIOENCODING": "utf8"}}],
        "latex-workshop.latex.recipe.default": "stack preview",
        "latex-workshop.latex.autoBuild.run": "onSave",
        "latex-workshop.latex.outDir": "%DIR%/../build/preview",
        "latex-workshop.view.pdf.viewer": "tab",
        "latex-workshop.latex.search.rootFiles.exclude": ["**/build/**"],
    }
    tasks = {"version": "2.0.0", "tasks": [
        {"label": "Preview this document (PDF)", "type": "process", "command": py, "args": run[1:] + ["${file}"],
         "group": {"kind": "build", "isDefault": True}, "problemMatcher": []},
        {"label": "Rebuild this document's web pages", "type": "process", "command": py, "args": run[1:] + ["${file}", "web"],
         "problemMatcher": []},
    ]}
    for name, new in (("settings.json", settings), ("tasks.json", tasks)):
        f = vs / name
        old = {}
        if f.exists():
            try:
                old = json.loads(f.read_text(encoding="utf8"))
            except json.JSONDecodeError:
                shutil.copy2(f, f.with_suffix(".json.bak"))  # keep a file we cannot parse (comments) rather than lose it
        if name == "tasks.json" and old.get("tasks"):
            labels = {t["label"] for t in new["tasks"]}
            new = {**old, "tasks": [t for t in old["tasks"] if t.get("label") not in labels] + new["tasks"]}
        else:
            new = {**old, **new}
        f.write_text(json.dumps(new, indent=2) + "\n", encoding="utf8")
    print("VS Code editing set up in", vs)
