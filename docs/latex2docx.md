# LaTeX to Word (`research_helpers.latex2docx`)

LaTeX to Word (.docx) through pandoc, with the numbering and cross-references of the PDF.

Command line:
    rh latex2docx main.tex out.docx [--csl style.csl] [--numbers generated/numbers.tex]
                  [--margins 40,25,25,25] [--font Arial] [--size 12] [--spacing 1.5] [--figure-width 15cm]

Python:
    from research_helpers.latex2docx import convert, PageSetup
    convert("thesis/main.tex", "Thesis.docx", csl="ulster-harvard-lhs.csl", page=PageSetup(left_mm: float = 25, right_mm: float = 25, top_mm: float = 25, bottom_mm: float = 25, font: str = 'Arial', size_pt: float = 12, line_spacing: float = 1.5, space_after_pt: float = 8, language: str = 'en-GB', heading_color: str = '000000', link_color: str = '000073', page_number: str = 'right') -> None)

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
A reference document with the page set-up (A4, margins, font, size, line spacing, space after paragraphs) is built
from pandoc's default by editing its XML, so Microsoft Word is not needed.

## Functions and classes


**`PageSetup(left_mm: float = 25, right_mm: float = 25, top_mm: float = 25, bottom_mm: float = 25, font: str = 'Arial', size_pt: float = 12, line_spacing: float = 1.5, space_after_pt: float = 8, language: str = 'en-GB', heading_color: str = '000000', link_color: str = '000073', page_number: str = 'right') -> None -> None`**

PageSetup(left_mm: float = 25, right_mm: float = 25, top_mm: float = 25, bottom_mm: float = 25, font: str = 'Arial', size_pt: float = 12, line_spacing: float = 1.5, space_after_pt: float = 8, language: str = 'en-GB', heading_color: str = '000000', link_color: str = '000073', page_number: str = 'right') -> None


**`convert(main_tex, out_docx, csl=None, numbers=(), page=None, figure_width='15cm', front_matter='', keep_intermediate=False)`**

Convert main_tex (and everything it inputs) to out_docx. Returns pandoc's exit code.


**`pandoc_exe()`**




**`reference_doc(dest, page, pandoc=None)`**

pandoc's default reference.docx with the page set-up written into its XML
