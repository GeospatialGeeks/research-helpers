# Results tables (`research_helpers.tables`)

Results as LaTeX tables (booktabs), written from data so that no number in a manuscript is typed by hand.

    from research_helpers.tables import latex_table, num
    tex = latex_table("baselines", "Predictive performance by feature set.",
                      ["Features", "Accuracy (\%)", "MAE"],
                      [["Satellite only", num(48.7, 1), num(6.3, 1)], "MID", ["+ form", num(51.5, 1), num(6.0, 1)]],
                      align="lrr", note="Spatial cross-validation.")
    open("generated/tables/baselines.tex", "w").write(tex)

    pending_table("embeddings", "satellite embedding comparison")    # placeholder with the same label

Conventions: the caption is above the table and the label is tab:<name>; "MID" in the rows inserts a \midrule; wide
tables are scaled to the text width (needs \usepackage{adjustbox}); tex() escapes &, %, _ and #. A pending table keeps
its label, so \ref and \cref resolve while results are still being produced.

## Functions and classes


**`from_dataframe(df, name, caption, columns=None, formats=None, align=None, note=None)`**

a pandas DataFrame as a table: columns {col: header}, formats {col: decimals}


**`latex_table(name, caption, header, rows, align, note=None, size='\\small', scale=True, placement='htbp')`**




**`num(v, d=2, missing='--')`**

format a number with d decimals; None / NaN -> missing


**`pending_table(name, what)`**




**`tex(s)`**




**`thousands(n)`**

12345 -> 12{,}345 (a thousands separator that LaTeX does not space as a list comma)
