"""The LaTeX-to-web helpers, without needing LaTeX or a site."""
import shutil

import pytest

from research_helpers import tex_web as T


def project(tmp_path, **kw):
    """A minimal conversion project in tmp_path."""
    return T.Project(root=tmp_path, aux=tmp_path / "a.aux", chapters=[], url="/c/", out=tmp_path, figures=tmp_path, **kw)


def test_close_brace_handles_nesting_and_escapes():
    """Matching braces handles nesting and escaped braces."""
    s = r"{a{b}\}c}d"
    assert s[:T.close_brace(s, 0)] == r"{a{b}\}c}"


def test_comments_stripped_but_escaped_percent_kept():
    """Comments are removed; escaped percent signs stay."""
    assert T.strip_comments("50\\% left % gone") == "50\\% left "


def test_labels_from_aux(tmp_path):
    """Labels and numbers are read from the aux file."""
    a = tmp_path / "a.aux"
    a.write_text(r"\newlabel{eq:x}{{3.2}{10}{}{equation.3.2}{}}")
    assert T.labels(a) == {"eq:x": "3.2"}


def test_figures_become_markers_with_caption_and_label(tmp_path):
    """Figures become placeholders with caption and label."""
    s, items = T.split_figures(r"Before \begin{figure}[ht]\draw;\caption{A cap}\label{fig:a}\end{figure} after", project(tmp_path))
    assert "FIGMARK0END" in s and "\\begin{figure}" not in s
    assert items[0][1:] == ("A cap", "fig:a")


def test_definitions_are_not_treated_as_figures(tmp_path):
    """Pictures inside macro definitions are not figures."""
    s, items = T.split_figures(r"\newcommand{\p}[1]{\begin{tikzpicture}\draw;\end{tikzpicture}}Text", project(tmp_path))
    assert items == [] and s == "Text"


def test_equations_get_printed_numbers(tmp_path):
    """Equations carry their printed numbers."""
    out = T.prepare(r"\begin{equation}x\label{e}\end{equation}", "3", {"e": "3.1"}, project(tmp_path))
    assert "\\tag{3.1}" in out and "{equation*}" in out


def test_sections_are_numbered_as_in_the_pdf(tmp_path):
    """Sections are numbered as in the PDF."""
    out = T.prepare(r"\section{A}\subsection{B}\section{C}", "4", {}, project(tmp_path))
    assert "\\section{4.1 A}" in out and "\\subsection{4.1.1 B}" in out and "\\section{4.2 C}" in out


def test_boxes_round_trip(tmp_path):
    """Coloured boxes survive conversion."""
    p = project(tmp_path, boxes={"keybox": ("key", "Key idea")})
    out = T.finish(T.prepare(r"\begin{keybox}Text\end{keybox}", "1", {}, p))
    assert '<div class="box box-key" markdown="1"><p class="box-title">Key idea</p>' in out and "</div>" in out


def test_units_leave_text_in_equations():
    """Units are moved out of bold text into maths."""
    assert T.units_out_of_text(r"\textbf{385\ensuremath{\mathrm{W}}}") == r"\textbf{385}{\mathrm{W}}\textbf{}"


@pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")
def test_cross_references_become_links(tmp_path):
    """Cross-references become links to their chapter."""
    out = T.to_markdown("See " + T.token("sec:a") + ".", project(tmp_path), {"sec:a": "ch1"}, {"sec:a": "2.1"})
    assert "[2.1](/c/ch1/#sec:a)" in out
