"""Results as LaTeX tables (booktabs), written from data so that no number in a manuscript is typed by hand.

    from research_helpers.tables import latex_table, num
    tex = latex_table("baselines", "Predictive performance by feature set.",
                      ["Features", "Accuracy (\\%)", "MAE"],
                      [["Satellite only", num(48.7, 1), num(6.3, 1)], "MID", ["+ form", num(51.5, 1), num(6.0, 1)]],
                      align="lrr", note="Spatial cross-validation.")
    open("generated/tables/baselines.tex", "w").write(tex)

    pending_table("embeddings", "satellite embedding comparison")    # placeholder with the same label

Conventions: the caption is above the table and the label is tab:<name>; "MID" in the rows inserts a \\midrule; wide
tables are scaled to the text width (needs \\usepackage{adjustbox}); tex() escapes &, %, _ and #. A pending table keeps
its label, so \\ref and \\cref resolve while results are still being produced.
"""
import math

__all__ = ["latex_table", "pending_table", "num", "tex", "thousands"]


def tex(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def num(v, d=2, missing="--"):
    """format a number with d decimals; None / NaN -> missing"""
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return missing
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return missing


def thousands(n):
    """12345 -> 12{,}345 (a thousands separator that LaTeX does not space as a list comma)"""
    return f"{int(n):,}".replace(",", "{,}")


def latex_table(name, caption, header, rows, align, note=None, size=r"\small", scale=True, placement="htbp"):
    lines = [rf"\begin{{table}}[{placement}]", r"\centering", size, rf"\caption{{{caption}}}\label{{tab:{name}}}"]
    if scale:
        lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    lines += [rf"\begin{{tabular}}{{{align}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for r in rows:
        lines.append(r"\midrule" if r == "MID" else " & ".join(str(x) for x in r) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    if scale:
        lines.append(r"\end{adjustbox}")
    if note:
        lines.append(rf"\par\smallskip\parbox{{0.95\linewidth}}{{\footnotesize {note}}}")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def pending_table(name, what):
    return (f"% table {name}: {what} not available yet\n\\begin{{table}}[htbp]\\centering\\small\n"
            f"\\caption{{Results pending: {tex(what)}.}}\\label{{tab:{name}}}\n"
            f"\\fbox{{\\parbox{{0.9\\linewidth}}{{\\centering The table is generated when the results are available.}}}}\n\\end{{table}}\n")


def from_dataframe(df, name, caption, columns=None, formats=None, align=None, note=None):
    """a pandas DataFrame as a table: columns {col: header}, formats {col: decimals}"""
    columns = columns or {c: tex(c) for c in df.columns}
    formats = formats or {}
    rows = [[num(r[c], formats[c]) if c in formats else tex(r[c]) for c in columns] for _, r in df.iterrows()]
    align = align or "l" + "r" * (len(columns) - 1)
    return latex_table(name, caption, list(columns.values()), rows, align, note=note)
