"""Literature-review helpers: database exports in, a de-duplicated, screened and described corpus out.

    from research_helpers.litreview import ingest, screen, bibliometrics
    rec, dups = ingest.load(scopus=["scopus.csv"], wos=["savedrecs.txt"])          # one schema, duplicates removed
    criteria = {"population": r"building|dwelling|housing", "outcome": r"energy (efficiency|performance)",
                "method": r"remote sens|satellite|lidar|gis"}
    rec = screen.apply(rec, criteria, rule=screen.all_of(["population", "outcome", "method"]))
    k = screen.cohen_kappa(rec["decision"], second_reviewer["decision"])          # agreement on a double-screened sample
    stats = bibliometrics.summary(rec[rec["include"]])                             # growth, sources, countries, keywords
    flow = screen.prisma_counts(identified=..., duplicates=len(dups), screened=len(rec), ...)

Built for systematic, scoping and bibliometric reviews (PRISMA 2020; Page et al. 2021, BMJ 372, n71). Rule-based
screening is transparent and repeatable: every decision records which criteria matched; borderline records can be
flagged for manual screening. Requires pandas (pip install "research-helpers[review]").
"""
from . import ingest, screen, bibliometrics  # noqa: F401
