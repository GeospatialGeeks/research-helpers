"""Research records: a data register and a reference of the scripts of a pipeline, built from what is on disk.

Command line:
    rh register data/ --out records/data_register.csv [--hash-limit-mb 200]
    rh scripts code/ --out records/pipeline_reference.md

Python:
    from research_helpers.records import data_register, script_reference
    reg = data_register("data")                       # list of dicts, one per folder with files
    md = script_reference(["ingest.py", "model.py"], root="code")

Data register: every folder below the root that holds files: number of files, size, row counts of Parquet tables
(if pyarrow is installed), file types, last change, the first lines of a SOURCE.txt in the folder (provenance), and
SHA-256 checksums of files below a size limit. Archive folders (_archive) are skipped. Keeping a SOURCE.txt (where the
data came from, when, under which licence) next to every download makes the register a complete provenance record.

Script reference: for each script, its command, its last git commit and its module docstring (the documentation of
what it reads, does and writes), as Markdown; a script documented in its docstring is documented everywhere.
"""
import ast, csv, datetime, hashlib, pathlib, re, subprocess

__all__ = ["data_register", "write_register", "script_reference", "sha256"]


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def data_register(root, hash_limit_mb=200, skip=("_archive", ".git", "__pycache__")):
    root = pathlib.Path(root)
    rows = []
    for d in sorted({p.parent for p in root.rglob("*") if p.is_file() and not any(s in p.parts for s in skip)}):
        files = [p for p in d.iterdir() if p.is_file() and not p.name.endswith((".part", ".aux.xml"))]
        if not files:
            continue
        src = (d / "SOURCE.txt").read_text(encoding="utf-8", errors="replace").strip().splitlines() if (d / "SOURCE.txt").exists() else []
        n_rows = 0
        for p in files:
            if p.suffix == ".parquet":
                try:
                    import pyarrow.parquet as pq
                    n_rows += pq.ParquetFile(p).metadata.num_rows
                except Exception:
                    pass
        sums = {p.name: sha256(p)[:16] for p in files if p.stat().st_size < hash_limit_mb * 1e6}
        rows.append({"folder": str(d.relative_to(root.parent)).replace("\\", "/"), "files": len(files),
                     "size_mb": round(sum(p.stat().st_size for p in files) / 1e6, 1), "table_rows": n_rows or "",
                     "types": ", ".join(sorted({p.suffix for p in files})),
                     "last_change": datetime.datetime.fromtimestamp(max(p.stat().st_mtime for p in files)).strftime("%Y-%m-%d"),
                     "source": " ".join(src[:2])[:300], "sha256_16": "; ".join(f"{k}:{v}" for k, v in sums.items())})
    return rows


def write_register(rows, out):
    out = pathlib.Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["folder"]); w.writeheader(); w.writerows(rows)
    return out


def _doc(p):
    t = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".py":
        try:
            return ast.get_docstring(ast.parse(t)) or ""
        except SyntaxError:
            return ""
    m = re.search(r"/\*(.*?)\*/", t, re.S) or re.search(r"^((?:#.*\n)+)", t)
    return re.sub(r"^\s*[*#] ?", "", m.group(1), flags=re.M).strip() if m else ""


def _git_last(p):
    r = subprocess.run(["git", "-C", str(p.parent), "log", "-1", "--format=%h %cs", "--", p.name], capture_output=True, text=True)
    return r.stdout.strip() or "not in git"


def script_reference(scripts, root=".", commands=None):
    """scripts: list of paths relative to root (in run order); commands: {script: typical command}"""
    root, commands = pathlib.Path(root), commands or {}
    md = ["# Pipeline reference\n"]
    for s in scripts:
        p = root / s
        if not p.exists():
            continue
        md.append(f"\n## `{s}`\n\nCommand: `{commands.get(s, 'python ' + s)}`  \nLast change: {_git_last(p)}\n\n```text\n{_doc(p)}\n```\n")
    return "\n".join(md)
