import shutil
from pathlib import Path

import pytest

from research_helpers import stack

DEMO = Path(__file__).parent.parent / "examples/demo"


def test_tokens_reach_latex(tmp_path):
    stack.write_tokens(tmp_path)
    text = (tmp_path / "rhtokens.tex").read_text()
    assert stack.tokens()["colour"]["accent"] in text
    assert r"\rhsectionbefore" in text


def test_check_reports_a_bad_name(tmp_path):
    shutil.copytree(DEMO, tmp_path / "p")
    (tmp_path / "p/figures").mkdir()
    (tmp_path / "p/figures/Final Map v2.png").write_bytes(b"")
    assert any("Final Map v2" in x for x in stack.check(tmp_path / "p"))


def test_check_passes_the_demo():
    assert stack.check(DEMO) == []


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="needs LaTeX")
@pytest.mark.parametrize("layout", ["manual", "report"])
def test_layouts_build(tmp_path, layout):
    shutil.copytree(DEMO, tmp_path / "p")
    result = stack.pdf(tmp_path / "p", layout)[layout]
    assert result["errors"] == []
    assert Path(result["pdf"]).stat().st_size > 1000
