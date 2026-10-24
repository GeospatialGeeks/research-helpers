# Changelog

## 0.1.0 - 2026-10-24

First release, generalised from the helpers of a PhD project on Earth observation and building energy efficiency
(Ulster University):
- `bib`: verified BibTeX from DOIs with optional title check; title search (publication types only); an author's works
  from OpenAlex; Zotero hand-off through the local connector, with a queue when Zotero is closed.
- `open_access`: open-access PDFs from OpenAlex, Semantic Scholar and arXiv (Elsevier TDM API with your own key), checked
  against the paper, with an audit log.
- `latex2docx`: LaTeX to Word through pandoc for articles and theses: numbered headings, tables and figures,
  cross-references as links, longtable / tabularx / adjustbox / \multicolumn, glossaries, conditional and result macros,
  journal front matter, PNG figures, citations with any CSL style, page set-up without Microsoft Word.
- `safeio`, `records`, `tables`, `spatial_cv`, `jobqueue`, `litreview` (ingest, screen, bibliometrics).
- Command line `rh`; offline tests.
