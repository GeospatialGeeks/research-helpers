"""Tests of the document stack: design tokens, checks and every layout building."""
import shutil
from pathlib import Path

import pytest

from research_helpers import stack

DEMO = Path(__file__).parent.parent / "examples/demo"


def test_tokens_reach_latex(tmp_path):
    """Design tokens are written for LaTeX."""
    stack.write_tokens(tmp_path)
    text = (tmp_path / "rhtokens.tex").read_text()
    assert stack.tokens()["colour"]["accent"] in text
    assert r"\rhsectionbefore" in text


def test_check_reports_a_bad_name(tmp_path):
    """The check reports a badly named file."""
    shutil.copytree(DEMO, tmp_path / "p")
    (tmp_path / "p/figures").mkdir()
    (tmp_path / "p/figures/Final Map v2.png").write_bytes(b"")
    assert any("Final Map v2" in x for x in stack.check(tmp_path / "p"))


def test_check_passes_the_demo():
    """The demo project passes the check."""
    assert stack.check(DEMO) == []


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="needs LaTeX")
@pytest.mark.parametrize("layout", ["manual", "report"])
def test_layouts_build(tmp_path, layout):
    """Every layout builds the demo."""
    shutil.copytree(DEMO, tmp_path / "p")
    result = stack.pdf(tmp_path / "p", layout)[layout]
    assert result["errors"] == []
    assert Path(result["pdf"]).stat().st_size > 1000


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs latexmk")
def test_own_layout_reads_the_projects_bibliography_and_reports_undefined(tmp_path):
    """BibTeX runs from the source folder, so a references.bib there is used even when the TeX distribution ships a
    file of the same name; a citation missing from it is reported, not hidden."""
    from research_helpers.stack import _own, load
    src = tmp_path / "paper"
    src.mkdir()
    (tmp_path / "document.toml").write_text('name = "t"\nlayouts = ["own"]\nsource = "paper"\n', encoding="utf8")
    (src / "references.bib").write_text("@misc{known2020, title={Known}, author={A. Author}, year={2020}}\n", encoding="utf8")
    (src / "main.tex").write_text(r"\documentclass{article}\begin{document}\cite{known2020} \cite{missing2021}"
                                  r"\bibliographystyle{plain}\bibliography{references}\end{document}" "\n", encoding="utf8")
    out = tmp_path / "build" / "own"
    out.mkdir(parents=True)
    r = _own(load(tmp_path), out)
    assert r["pdf"]
    assert r["undefined"] == ["missing2021"]
