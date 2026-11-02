import pytest

from research_helpers.autotex import fmt, macro_name, write_values


def test_macro_names_hold_letters_only():
    assert macro_name("karakoram_2012") == "karakoramTwoZeroOneTwo"
    assert macro_name("Hindu Kush km2") == "hinduKushKmTwo"


def test_formats():
    assert fmt(265500) == "265{,}500"
    assert fmt((0.1853, 2)) == "0.19"
    assert fmt("Sen") == "Sen"


def test_clash_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        write_values(tmp_path / "v.tex", {"a b": 1, "a_b": 2})


def test_file(tmp_path):
    p = write_values(tmp_path / "x" / "v.tex", {"n": 1200})
    assert "\\newcommand{\\n}{1{,}200}" in p.read_text()
