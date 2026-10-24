# Changelog

## 0.2.0 - 2026-10-24

`latex2docx`, Word output closer to the PDF:
- the contents and the lists of figures and tables become Word fields (Word fills them in when the file is opened);
- chapter documents start each chapter (top-level heading) on a new page;
- the title page (`front_matter`) is centred;
- a page number in the header (`PageSetup.page_number`, "right" by default);
- heading and link colours (`PageSetup.heading_color`, `PageSetup.link_color`), black headings by default.

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
