# Changelog

## 0.3.0 - 2026-10-24

`latex2docx`, Word output laid out like the PDF:
- title page as in the PDF (`TitlePage`: sizes, gaps, statement at the foot of the page), with no page number;
  roman page numbers for the preliminary pages and arabic from the main matter;
- headings at the sizes of the LaTeX class, chapter openings "Chapter 3" / title on two lines; contents with bold
  chapter entries; "Contents" and list titles no longer listed in the contents;
- booktabs tables (rules above, below and under the header row; single-spaced, centred), captions with bold label and
  colon, justified body text with the PDF's paragraph spacing, reference list with hanging indent;
- figures keep their width from the PDF (`0.7\linewidth`); a figure that exists only as PDF is rendered to PNG;
- publisher templates: `Profile` and `ieee_profile()` (`--profile ieee`): IEEE conference Word template, two columns,
  authors and affiliations from IEEEtran, "Abstract—" and "Index Terms—", headings, captions and references numbered
  by the template, "Fig. 1" / "Table I" in cross-references; `--reference-docx` for any Word template;
- valid Office Open XML: settings and table styles in schema order, image content types; dangling header and footer
  references from a template removed.

`templates` (new): `rh template list | fetch | new`: IEEEtran (conference and journal starters), the IGARSS paper kit
(LaTeX and IEEE conference Word templates), elsarticle, and CSL styles (IEEE, APA, Elsevier, Cite Them Right, MDPI,
Nature, Springer), each with its source, date, checksum and licence.

`tools/make_docs.py`: the guides in `docs/` are written from the docstrings.

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
