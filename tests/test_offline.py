"""Offline tests (no network): run with  python -m pytest -q"""
import pathlib

import numpy as np
import pandas as pd

from research_helpers.safeio import keep
from research_helpers.tables import latex_table, num, pending_table, thousands
from research_helpers.spatial_cv import block_folds, AreaOfApplicability
from research_helpers.litreview import ingest, screen, bibliometrics
from research_helpers.latex2docx import _number, _tables


def test_keep_archives(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("1")
    keep(p).write_text("2")
    arch = list((tmp_path / "_archive").rglob("a.csv"))
    assert p.read_text() == "2" and len(arch) == 1 and arch[0].read_text() == "1"


def test_tables():
    t = latex_table("x", "Cap.", ["A", "B"], [["a", num(1.234, 1)], "MID", ["b", "--"]], "lr", note="n")
    assert r"\label{tab:x}" in t and "1.2" in t and r"\midrule" in t
    assert r"\label{tab:y}" in pending_table("y", "later")
    assert thousands(12345) == "12{,}345" and num(float("nan")) == "--"


def test_block_folds():
    rng = np.random.default_rng(0)
    x, y = rng.uniform(0, 10000, 500), rng.uniform(0, 10000, 500)
    f = block_folds(x, y, 2000, k=5, seed=1)
    assert set(f) == set(range(5))
    blocks = (np.floor(x / 2000).astype(int), np.floor(y / 2000).astype(int))
    for bx, by in set(zip(*blocks)):                                     # every block in exactly one fold
        m = (blocks[0] == bx) & (blocks[1] == by)
        assert len(set(f[m])) == 1


def test_aoa():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 3))
    aoa = AreaOfApplicability().fit(X)
    di, out = aoa.predict(np.array([[0, 0, 0], [20, 20, 20]]))
    assert not out[0] and out[1]


def test_screen_and_kappa():
    rec = pd.DataFrame({"title": ["Satellite mapping of building energy efficiency", "A review of heat pumps"],
                        "abstract": ["", ""], "year": [2020, 2021]})
    crit = {"pop": "building", "out": "energy efficiency", "geo": "satellite", "rev": r"\breview\b"}
    r = screen.apply(rec, crit, rule=screen.all_of(["pop", "out", "geo"]), exclude_if=["rev"])
    assert list(r["include"]) == [True, False]
    assert screen.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    c = screen.prisma_counts(100, 10, 90, 70, 20, 2, 18, {"wrong outcome": 8}, 10)
    assert c["checks"] == ["consistent"]


def test_dedup_and_bibliometrics():
    a = pd.DataFrame({"rid": ["1", "2"], "db": ["Scopus", "Scopus"], "doi": ["10.1/A", None], "title": ["Same title", "Other"],
                      "abstract": ["x", "y"], "year": [2020, 2021], "source_title": ["J", "J"], "doc_type": ["Article"] * 2,
                      "cited_by": [3, 1], "affiliations": ["Uni, Belfast, UK", "Uni, Dublin, Ireland"], "author_keywords": ["EPC; GIS", "GIS"]})
    b = a.iloc[[0]].assign(rid="W1", db="WoS", doi="https://doi.org/10.1/a")
    rec, dups = ingest.deduplicate(pd.concat([a, b], ignore_index=True))
    assert len(rec) == 2 and len(dups) == 1 and dups["reason"].iat[0] == "same DOI"
    s = bibliometrics.summary(rec)
    assert s["documents"] == 2 and s["keywords"]["gis"] == 2 and "United Kingdom" in s["countries"]


def test_numbering():
    body = (r"\chapter{Intro}\label{ch:i}\section{A}\label{s:a}\begin{table}\caption{T}\label{tab:t}\end{table}"
            r"\appendix\chapter{Data}\label{app:d}")
    out, names = _number(body, chapters=True)
    assert names["ch:i"] == "Chapter 1" and names["s:a"] == "Section 1.1" and names["tab:t"] == "Table 1.1" and names["app:d"] == "Appendix A"
    assert r"\begin{tabular}{lr}" in _tables(r"\begin{tabularx}{\linewidth}{Xr}x&y\end{tabularx}")
