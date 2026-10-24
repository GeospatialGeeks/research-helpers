"""Transparent rule-based screening, agreement between reviewers and PRISMA 2020 counts.

    criteria = {"population": r"building|dwelling|housing", "outcome": r"energy (efficiency|performance)|heat loss",
                "method": r"remote sens|satellite|lidar|\\bgis\\b", "review": r"\\b(systematic|literature) review\\b"}
    rec = apply(rec, criteria, rule=all_of(["population", "outcome", "method"]), exclude_if=["review"])
    rec[["title", "include", "matched", "decision"]]

Each criterion is a regular expression tested (case-insensitively) on title, abstract and keywords. `rule` decides
inclusion from the set of matched criteria; `exclude_if` lists criteria that exclude a record whatever else matches;
`flag_if` marks records for manual screening. Every record keeps the list of criteria it matched, so each decision can
be explained and audited, and the rules can be refined and re-run.

Reviewer agreement: cohen_kappa(a, b) on a double-screened sample (report it with the sample size).
PRISMA: prisma_counts(...) returns the numbers of the PRISMA 2020 flow diagram (Page et al. 2021).
"""
import re

import pandas as pd

TEXT_COLS = ("title", "abstract", "author_keywords", "index_keywords")


def text_of(r, cols=TEXT_COLS):
    return " ".join(str(r.get(c, "") or "") for c in cols if str(r.get(c, "") or "") != "nan")


def all_of(names):
    names = set(names)
    return lambda m: names <= m


def any_of(names):
    names = set(names)
    return lambda m: bool(names & m)


def apply(rec, criteria, rule, exclude_if=(), flag_if=(), cols=TEXT_COLS):
    comp = {k: re.compile(v, re.I) for k, v in criteria.items()}
    matched, include, decision, flag = [], [], [], []
    for _, r in rec.iterrows():
        t = text_of(r, cols)
        m = {k for k, p in comp.items() if p.search(t)}
        ex = bool(set(exclude_if) & m)
        inc = rule(m) and not ex
        matched.append("; ".join(sorted(m))); include.append(inc); flag.append(bool(set(flag_if) & m))
        decision.append("included" if inc else ("excluded: " + ", ".join(sorted(set(exclude_if) & m)) if ex else "excluded: criteria not met"))
    return rec.assign(matched=matched, include=include, flag_for_manual=flag, decision=decision)


def cohen_kappa(a, b):
    a, b = pd.Series(list(a)), pd.Series(list(b))
    cats = sorted(set(a) | set(b))
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def prisma_counts(identified_db, duplicates, screened, excluded_screening, sought, not_retrieved, assessed,
                  excluded_fulltext_reasons, included, identified_other=0):
    """numbers of the PRISMA 2020 flow diagram, checked for consistency"""
    c = {"identified_databases": identified_db, "identified_other_methods": identified_other, "duplicates_removed": duplicates,
         "records_screened": screened, "records_excluded": excluded_screening, "reports_sought": sought,
         "reports_not_retrieved": not_retrieved, "reports_assessed": assessed,
         "reports_excluded": sum(excluded_fulltext_reasons.values()), "reports_excluded_reasons": excluded_fulltext_reasons,
         "studies_included": included}
    problems = []
    if identified_db - duplicates != screened:
        problems.append("identified - duplicates != screened")
    if screened - excluded_screening != sought:
        problems.append("screened - excluded != sought")
    if sought - not_retrieved != assessed:
        problems.append("sought - not retrieved != assessed")
    if assessed - c["reports_excluded"] != included:
        problems.append("assessed - excluded != included")
    c["checks"] = problems or ["consistent"]
    return c
