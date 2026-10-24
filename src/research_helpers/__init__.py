"""research-helpers: everyday helpers for reproducible research.

Modules (import only what you need; heavy dependencies are optional):
    safeio          keep(): never overwrite an output, archive the earlier version
    bib             verified BibTeX from DOIs (Crossref), title search, author works (OpenAlex), Zotero hand-off
    open_access     find and download open-access PDFs for DOIs, and check that a PDF is the right paper
    latex2docx      LaTeX to Word through pandoc, laid out like the PDF or on a publisher's Word template
    templates       library of paper templates and citation styles from official sources; new papers from them
    tables          results tables (pandas DataFrame or rows) as LaTeX booktabs tables
    records         data register (sizes, checksums, sources) and a reference of scripts from their docstrings
    spatial_cv      spatial block folds and the area of applicability of a model
    jobqueue        run long jobs one after another, after a condition, with a log
    litreview       literature review: ingest Scopus / Web of Science, de-duplicate, rule-based screening, bibliometrics
"""
__version__ = "0.3.0"
