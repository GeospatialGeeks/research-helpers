"""Descriptive bibliometrics of a corpus (the science-mapping summary of a review).

    from research_helpers.litreview.bibliometrics import summary
    s = summary(rec)            # dict: documents per year, growth rate, sources, countries, keywords, most cited

Growth: the compound annual growth rate between a base year and the last complete year,
CAGR = (n_end / n_base)^(1 / (end - base)) - 1. The last year of a corpus is usually incomplete and is left out.
Countries are taken from the affiliations (the last comma-separated part of each address) with common spellings
harmonised; check the result for your corpus. Keywords are the author keywords, lower case, counted once per record.
For network maps (co-authorship, co-citation, keyword co-occurrence) export the corpus for VOSviewer (van Eck and
Waltman 2010) or bibliometrix (Aria and Cuccurullo 2017).
"""
import collections

import pandas as pd

CNORM = {"England": "United Kingdom", "Scotland": "United Kingdom", "Wales": "United Kingdom", "Northern Ireland": "United Kingdom",
         "UK": "United Kingdom", "USA": "United States", "Türkiye": "Turkey", "Korea": "South Korea", "Republic of Korea": "South Korea",
         "Hong Kong": "China", "Macao": "China", "Macau": "China", "Russian Federation": "Russia", "Viet Nam": "Vietnam",
         "Peoples R China": "China", "U Arab Emirates": "United Arab Emirates"}


def countries(aff):
    if not isinstance(aff, str):
        return []
    out = []
    for part in aff.split(";"):
        c = part.split(",")[-1].strip().rstrip(".")
        c = CNORM.get(c, c)
        if c and len(c) < 40 and c not in out:
            out.append(c)
    return out


def cagr(by_year, base=None, end=None):
    years = sorted(by_year)
    base = base or years[0]
    if end is None:
        end = years[-2] if len(years) > 1 else years[-1]          # the last year is usually incomplete
    n0, n1 = by_year.get(base, 0), by_year.get(end, 0)
    return round(100 * ((n1 / n0) ** (1 / max(end - base, 1)) - 1), 1) if n0 else None, base, end


def summary(rec, top=10, base_year=None):
    df = rec.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]); df["year"] = df["year"].astype(int)
    by_year = df["year"].value_counts().sort_index().to_dict()
    g, b, e = cagr(by_year, base=base_year)
    ctry = collections.Counter(c for a in df.get("affiliations", pd.Series(dtype=str)) for c in countries(a))
    kw = collections.Counter(k for ks in df.get("author_keywords", pd.Series(dtype=str)).dropna()
                             for k in {x.strip().lower() for x in str(ks).split(";") if x.strip()})
    cited = df.sort_values("cited_by", ascending=False).head(top)[["title", "year", "source_title", "cited_by"]] if "cited_by" in df else None
    return {"documents": int(len(df)), "by_year": by_year, "cagr_pct": g, "cagr_years": [b, e],
            "sources": df["source_title"].value_counts().head(top).to_dict() if "source_title" in df else {},
            "n_sources": int(df["source_title"].nunique()) if "source_title" in df else 0,
            "countries": dict(ctry.most_common(top)), "keywords": dict(kw.most_common(top)),
            "most_cited": cited.to_dict("records") if cited is not None else []}
