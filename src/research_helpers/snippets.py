"""Put real code and worked values into LaTeX documents, taken from the source so they cannot drift.

    function_listing("code/x.py", "heat", "out/heat.tex")        one Python function, captioned with its file and lines
    around_listing("code/x.js", "NDVI", "out/ndvi.tex")          the lines around the first match of a pattern
    table_tex(rows, ["Column", "Value"], "out/table.tex", "lX")  a table from rows, with text escaped
    check_literal("code/x.py", "0.33")                           stops the build if a stated constant has left the code
"""
import ast
import re
from pathlib import Path

ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape(s):
    return "".join(ESC.get(c, c) for c in str(s))


def _ascii(text):
    return text.encode("ascii", "replace").decode().replace("?", "?")


def _write(lines, first, label, out):
    body = _ascii("\n".join(x[:108] for x in lines))
    head = rf"\snippetcaption{{{escape(label)}, lines {first}--{first + len(lines) - 1}}}"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(f"{head}\n\\begin{{lstlisting}}[firstnumber={first}]\n{body}\n\\end{{lstlisting}}\n", encoding="utf8")
    return out


def function_listing(path, name, out, label=None):
    path = Path(path)
    source = path.read_text(encoding="utf8")
    node = next((n for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name), None)
    if node is None:
        raise ValueError(f"{name} is not in {path}")
    lines = source.splitlines()[node.lineno - 1:node.end_lineno]
    return _write(lines, node.lineno, label or f"{path.name}, {name}()", out)


def around_listing(path, pattern, out, before=2, after=8, label=None):
    path = Path(path)
    lines = path.read_text(encoding="utf8", errors="replace").splitlines()
    i = next((k for k, l in enumerate(lines) if re.search(pattern, l)), None)
    if i is None:
        raise ValueError(f"{pattern} is not in {path}")
    a = max(i - before, 0)
    return _write(lines[a:i + after + 1], a + 1, label or path.name, out)


def check_literal(path, literal):
    if literal not in Path(path).read_text(encoding="utf8", errors="replace"):
        raise ValueError(f"{literal} is no longer in {path}")


def table_tex(rows, header, out, spec, raw_columns=()):
    """Tabularx body. Columns listed in raw_columns hold LaTeX and are not escaped."""
    cell = lambda j, v: str(v) if j in raw_columns else escape(v)
    body = "\n".join(" & ".join(cell(j, v) for j, v in enumerate(r)) + r" \\" for r in rows)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(f"\\begin{{tabularx}}{{\\linewidth}}{{@{{}}{spec}@{{}}}}\\toprule\n" + " & ".join(header) + r" \\\midrule" + f"\n{body}\n\\bottomrule\\end{{tabularx}}\n", encoding="utf8")
    return out
