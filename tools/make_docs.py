"""Write the guides in docs/ from the docstrings: module description, then each public function and class.

    python tools/make_docs.py

Run after changing a docstring, so the guides and the code say the same.
"""
import importlib, inspect, pathlib, pkgutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TITLES = {
    "bib": "Verified references", "open_access": "Open-access full texts", "latex2docx": "LaTeX to Word",
    "safeio": "Never overwrite", "records": "Research records", "tables": "Results tables",
    "spatial_cv": "Spatial cross-validation and area of applicability", "jobqueue": "Job queue",
    "litreview": "Literature review", "templates": "Paper templates and citation styles",
}


def members(mod):
    names = getattr(mod, "__all__", None) or [n for n in dir(mod) if not n.startswith("_")]
    out = []
    for n in sorted(names):
        obj = getattr(mod, n, None)
        if (inspect.isfunction(obj) or inspect.isclass(obj)) and getattr(obj, "__module__", "") == mod.__name__:
            out.append((n, obj))
    return out


def entries(mod):
    text = []
    for n, obj in members(mod):
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = "()"
        doc = inspect.getdoc(obj) or ""
        if inspect.isclass(obj) and doc.startswith(n + "("):           # dataclass without its own docstring
            doc = ""
        text.append(f"\n**`{n}{sig}`**\n\n{doc}\n")
    return "".join(text)


def module_doc(name):
    mod = importlib.import_module(f"research_helpers.{name}")
    head = f"# {TITLES.get(name, name)} (`research_helpers.{name}`)\n\n{inspect.getdoc(mod) or ''}\n\n## Functions and classes\n"
    if hasattr(mod, "__path__"):                                        # a sub-package: one section per module
        body = ""
        for sub in sorted(m.name for m in pkgutil.iter_modules(mod.__path__)):
            sm = importlib.import_module(f"research_helpers.{name}.{sub}")
            body += f"\n\n### `research_helpers.{name}.{sub}`\n\n{inspect.getdoc(sm) or ''}\n" + entries(sm)
        return head + body
    return head + entries(mod)


if __name__ == "__main__":
    for name in TITLES:
        p = DOCS / f"{name}.md"
        p.write_text(module_doc(name).rstrip() + "\n", encoding="utf-8")
        print(p.relative_to(ROOT))
