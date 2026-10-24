# LaTeX to Word (`research_helpers.latex2docx`)

LaTeX to Word (.docx) through pandoc, with the numbering and cross-references of the PDF.

Command line:
    rh latex2docx main.tex out.docx [--csl style.csl] [--numbers generated/numbers.tex]
                  [--margins 40,25,25,25] [--font Arial] [--size 12] [--spacing 1.5] [--figure-width 15cm]
    rh latex2docx paper.tex paper.docx --csl ieee.csl --profile ieee      IEEE conference paper on IEEE's Word template

Python:
    from research_helpers.latex2docx import convert, PageSetup, TitlePage, ieee_profile
    convert("thesis/main.tex", "Thesis.docx", csl="ulster-harvard-lhs.csl", page=PageSetup(left_mm=40),
            front_matter=title_page_latex, title_page=TitlePage())
    convert("paper/main.tex", "paper.docx", csl="ieee.csl", profile=ieee_profile())

Requirements: pandoc (2.11 or later) on the PATH or in RH_PANDOC.

pandoc reads LaTeX but does not number chapters, sections, tables or figures, resolve \ref / \cref, or read
longtable, tabularx, adjustbox, \multicolumn, glossaries and many layout commands reliably. The converter therefore
flattens the document first:
  - every \input / \include / \InputIfFileExists is inlined (relative to the main file); comments are removed;
  - headings get the numbers of the PDF: reports and books "Chapter 3. Title", "3.2 Title", "3.2.1 Title"; articles
    "2 Title", "2.1 Title"; after \appendix "Appendix A. Title", "A.1 Title";
  - tables and figures with a caption are numbered ("Table 3.2", or "Table 4" in articles) and every \ref, \cref
    or \Cref becomes a link to the bookmark of its target, with the same text as in the PDF;
  - longtable, tabularx and adjustbox become plain tabular, \multicolumn becomes text and empty cells;
  - \includegraphics without an extension takes the PNG beside the PDF figure (Word cannot embed PDF);
  - result macros (\newcommand / \renewcommand{\Name}{value} in the --numbers files) become their values;
  - glossaries acronyms (\newacronym) become a table of abbreviations where \printglossary stood;
  - citations are rendered by pandoc citeproc from the .bib files named in \bibliography, with the CSL style given
    (titles keep their capitals; pandoc would otherwise put BibTeX titles in sentence case).
  - a figure that exists only as PDF is rendered to PNG (pdftoppm, or PyMuPDF), at the width it has in the PDF.
A reference document is built from pandoc's default by editing its XML, so Microsoft Word is not needed: page set-up
(margins, font, size, line spacing, paragraph spacing, justified text), headings at the sizes of the LaTeX class, each
chapter on a new page, booktabs tables (rules above, below and under the header, single-spaced rows), captions with
bold labels, a reference list with hanging indent, and page numbers in the header. After pandoc, the Word XML gets the
contents and lists of figures and tables as Word fields, a title page laid out like the PDF's (TitlePage), no page
number on it, roman page numbers for the preliminary pages and arabic from the main matter.

Publisher templates: with a Profile (e.g. ieee_profile()), the publisher's Word template supplies the styles and page
set-up; pandoc's styles are mapped onto the template's, the text is set in its columns after the title block, and
headings, captions and references are left for the template to number ("I. Introduction", "Fig. 1.", "[1]").

## Functions and classes

**`PageSetup(left_mm: float = 25, right_mm: float = 25, top_mm: float = 25, bottom_mm: float = 25, font: str = 'Arial', size_pt: float = 12, line_spacing: float = 1.5, space_after_pt: float = 8, language: str = 'en-GB', heading_color: str = '000000', link_color: str = '000073', page_number: str = 'right', justify: bool = True, caption_size_pt: float = 11, table_size_pt: float = 0, booktabs: bool = True) -> None`**



**`Profile(reference_docx: str, styles: dict = <factory>, columns: int = 1, column_space_pt: float = 18, number_headings: bool = True, caption_labels: bool = True, section_name: str = 'Section {n}', figure_name: str = 'Figure {n}', table_name: str = 'Table {n}', strip_reference_numbers: bool = False, abstract_label: str = '', keywords_label: str = '', column_width_cm: float = 0, text_width_cm: float = 0) -> None`**

A publisher's Word template and how the converted paper maps onto it.
styles: pandoc paragraph style id -> template style id; columns: text columns after the title block;
number_headings / caption_labels: False when the template numbers headings / captions itself (then the numbers are
left out of the text); *_name: how cross-references name sections, figures and tables ({n} number, {r} roman);
strip_reference_numbers: remove "[1]" from reference-list entries when the template's style numbers them;
column_width_cm / text_width_cm: widths for \columnwidth and \textwidth figures.

**`TitlePage(sizes_pt: tuple = (17.28, 14.4), gaps_mm: tuple = (0, 20, 15, 10, 10), bottom: int = 1, numbered: bool = False) -> None`**

Layout of the front matter given to convert(front_matter=...): one paragraph per item, centred.
sizes_pt: font sizes of the first paragraphs (title, author, ...); gaps_mm: space above each paragraph;
bottom: number of trailing paragraphs set at the foot of the page (e.g. a word-count statement);
numbered: show a page number on the title page.

**`convert(main_tex, out_docx, csl=None, numbers=(), page=None, figure_width='15cm', front_matter='', keep_intermediate=False, title_page=None, reference_docx=None, profile=None)`**

Convert main_tex (and everything it inputs) to out_docx. Returns pandoc's exit code.
front_matter: LaTeX for the first page (the title page of the PDF is not converted); title_page: a TitlePage to lay
it out like a title page (otherwise its paragraphs are only centred); reference_docx: a publisher's Word template
whose styles and page set-up are used instead of the generated ones (page is then ignored for styles); profile: a
Profile (e.g. ieee_profile()) that also maps the styles, columns and numbering onto that template.

**`ieee_profile(reference_docx=None)`**

IEEE conference paper (A4 by default) on IEEE's own Word template: two columns, headings I / A numbered by the
template, "Fig. 1." and "TABLE I" captions and numbered references from its styles. The template is taken from the
research-helpers template library (rh template fetch igarss-2026) unless given.
