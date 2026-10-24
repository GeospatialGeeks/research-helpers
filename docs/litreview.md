# Literature review (`research_helpers.litreview`)

Literature-review helpers: database exports in, a de-duplicated, screened and described corpus out.

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

## Functions and classes


### `research_helpers.litreview.ingest`

Read Scopus (CSV) and Web of Science (tab-delimited) exports into one schema and remove duplicates.

    from research_helpers.litreview.ingest import load
    rec, dups = load(scopus=glob("exports/scopus*.csv"), wos=glob("exports/savedrecs*.txt"))

Schema: rid, db, doi, title, abstract, author_keywords, index_keywords, authors, year, source_title, doc_type,
cited_by, affiliations, references, language, open_access, plus doi_n and title_n (normalised for matching) and
found_in (databases that held the record). Duplicates are found by record id, then by normalised DOI, then by
normalised title and year; the Scopus record and the longer abstract are kept. `dups` lists every removed record with
the reason, for the PRISMA identification box.

Scopus export: "CSV" with all citation, bibliographical, abstract and keyword fields. Web of Science export:
"Tab delimited file", full record and cited references.


**`deduplicate(allr)`**




**`load(scopus=(), wos=())`**

read the exports and remove duplicates: (records, duplicates)


**`norm_doi(d)`**




**`norm_title(t)`**




**`query_blocks(query_text, max_blocks=None)`**

concept blocks of a Scopus TITLE-ABS-KEY(...) AND TITLE-ABS-KEY(...) query as compiled regular expressions
(truncation * becomes word characters), to check which records a query would retrieve


**`read_scopus(files)`**




**`read_wos(files)`**




### `research_helpers.litreview.screen`

Transparent rule-based screening, agreement between reviewers and PRISMA 2020 counts.

    criteria = {"population": r"building|dwelling|housing", "outcome": r"energy (efficiency|performance)|heat loss",
                "method": r"remote sens|satellite|lidar|\bgis\b", "review": r"\b(systematic|literature) review\b"}
    rec = apply(rec, criteria, rule=all_of(["population", "outcome", "method"]), exclude_if=["review"])
    rec[["title", "include", "matched", "decision"]]

Each criterion is a regular expression tested (case-insensitively) on title, abstract and keywords. `rule` decides
inclusion from the set of matched criteria; `exclude_if` lists criteria that exclude a record whatever else matches;
`flag_if` marks records for manual screening. Every record keeps the list of criteria it matched, so each decision can
be explained and audited, and the rules can be refined and re-run.

Reviewer agreement: cohen_kappa(a, b) on a double-screened sample (report it with the sample size).
PRISMA: prisma_counts(...) returns the numbers of the PRISMA 2020 flow diagram (Page et al. 2021).


**`all_of(names)`**




**`any_of(names)`**




**`apply(rec, criteria, rule, exclude_if=(), flag_if=(), cols=('title', 'abstract', 'author_keywords', 'index_keywords'))`**




**`cohen_kappa(a, b)`**




**`prisma_counts(identified_db, duplicates, screened, excluded_screening, sought, not_retrieved, assessed, excluded_fulltext_reasons, included, identified_other=0)`**

numbers of the PRISMA 2020 flow diagram, checked for consistency


**`text_of(r, cols=('title', 'abstract', 'author_keywords', 'index_keywords'))`**




### `research_helpers.litreview.bibliometrics`

Descriptive bibliometrics of a corpus (the science-mapping summary of a review).

    from research_helpers.litreview.bibliometrics import summary
    s = summary(rec)            # dict: documents per year, growth rate, sources, countries, keywords, most cited

Growth: the compound annual growth rate between a base year and the last complete year,
CAGR = (n_end / n_base)^(1 / (end - base)) - 1. The last year of a corpus is usually incomplete and is left out.
Countries are taken from the affiliations (the last comma-separated part of each address) with common spellings
harmonised; check the result for your corpus. Keywords are the author keywords, lower case, counted once per record.
For network maps (co-authorship, co-citation, keyword co-occurrence) export the corpus for VOSviewer (van Eck and
Waltman 2010) or bibliometrix (Aria and Cuccurullo 2017).


**`cagr(by_year, base=None, end=None)`**




**`countries(aff)`**




**`summary(rec, top=10, base_year=None)`**


