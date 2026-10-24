"""Read Scopus (CSV) and Web of Science (tab-delimited) exports into one schema and remove duplicates.

    from research_helpers.litreview.ingest import load
    rec, dups = load(scopus=glob("exports/scopus*.csv"), wos=glob("exports/savedrecs*.txt"))

Schema: rid, db, doi, title, abstract, author_keywords, index_keywords, authors, year, source_title, doc_type,
cited_by, affiliations, references, language, open_access, plus doi_n and title_n (normalised for matching) and
found_in (databases that held the record). Duplicates are found by record id, then by normalised DOI, then by
normalised title and year; the Scopus record and the longer abstract are kept. `dups` lists every removed record with
the reason, for the PRISMA identification box.

Scopus export: "CSV" with all citation, bibliographical, abstract and keyword fields. Web of Science export:
"Tab delimited file", full record and cited references.
"""
import html, re, unicodedata
import pandas as pd

SCHEMA = ["rid", "db", "doi", "title", "abstract", "author_keywords", "index_keywords", "authors", "year", "source_title",
          "doc_type", "cited_by", "affiliations", "references", "language", "open_access"]
WOS_DT = {"Article": "Article", "Review": "Review", "Proceedings Paper": "Conference Paper", "Article; Proceedings Paper": "Conference Paper",
          "Review; Early Access": "Review", "Article; Early Access": "Article"}
DT_CANON = {"article": "Article", "review": "Review", "conference paper": "Conference Paper", "data paper": "Data Paper"}


def norm_title(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def norm_doi(d):
    if not isinstance(d, str) or not d.strip():
        return ""
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d.strip().lower())


def read_scopus(files):
    frames = []
    for f in files:
        d = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
        for c in ("Title", "Abstract", "Author Keywords", "Index Keywords", "Source title"):
            if c in d:
                d[c] = d[c].map(lambda x: html.unescape(x) if isinstance(x, str) else x)
        frames.append(pd.DataFrame({
            "rid": d.get("EID"), "db": "Scopus", "doi": d.get("DOI"), "title": d.get("Title"), "abstract": d.get("Abstract"),
            "author_keywords": d.get("Author Keywords"), "index_keywords": d.get("Index Keywords"), "authors": d.get("Authors"),
            "year": d.get("Year"), "source_title": d.get("Source title"), "doc_type": d.get("Document Type"),
            "cited_by": d.get("Cited by"), "affiliations": d.get("Affiliations"), "references": d.get("References"),
            "language": d.get("Language of Original Document"), "open_access": d.get("Open Access")}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=SCHEMA)


def read_wos(files):
    frames = []
    for f in files:
        d = pd.read_csv(f, sep="\t", quoting=3, dtype=str, encoding="utf-8-sig", index_col=False)
        g = lambda c: d[c] if c in d else None
        aff = g("C1")
        if aff is not None:
            aff = aff.fillna("").str.replace(r"\[[^\]]*\]\s*", "", regex=True)
        frames.append(pd.DataFrame({
            "rid": g("UT"), "db": "WoS", "doi": g("DI"), "title": g("TI"), "abstract": g("AB"), "author_keywords": g("DE"),
            "index_keywords": g("ID"), "authors": g("AU"), "year": pd.to_numeric(g("PY"), errors="coerce"), "source_title": g("SO"),
            "doc_type": g("DT").map(lambda x: WOS_DT.get(x, x)) if g("DT") is not None else None,
            "cited_by": pd.to_numeric(g("TC"), errors="coerce"), "affiliations": aff, "references": g("CR"),
            "language": g("LA"), "open_access": g("OA")}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=SCHEMA)


def deduplicate(allr):
    allr = allr.copy()
    allr["doi_n"] = allr["doi"].map(norm_doi)
    allr["title_n"] = allr["title"].map(norm_title)
    allr["year"] = pd.to_numeric(allr["year"], errors="coerce").astype("Int64")
    allr["cited_by"] = pd.to_numeric(allr["cited_by"], errors="coerce").fillna(0)
    allr["doc_type"] = allr["doc_type"].map(lambda x: DT_CANON.get(str(x).strip().lower(), x))
    allr["prio"] = (allr["db"] != "Scopus").astype(int)
    allr["abs_len"] = allr["abstract"].fillna("").str.len()
    allr = allr.sort_values(["prio", "abs_len"], ascending=[True, False]).reset_index(drop=True)
    within = allr.duplicated(subset=["rid"]) & allr["rid"].notna()
    by_doi = allr["doi_n"].ne("") & allr.duplicated(subset=["doi_n"])
    by_title = allr["title_n"].ne("") & allr.duplicated(subset=["title_n", "year"])
    dup = within | by_doi | by_title
    dups = allr.loc[dup, ["rid", "db", "doi", "title", "year"]].assign(
        reason=["same record id" if a else "same DOI" if b else "same title and year" for a, b in zip(within[dup], by_doi[dup])])
    rec = allr[~dup].copy()
    key = lambda d: d["doi_n"].where(d["doi_n"] != "", d["title_n"] + "|" + d["year"].astype(str))
    allr["k"], rec["k"] = key(allr), key(rec)
    rec["found_in"] = rec["k"].map(allr.groupby("k")["db"].agg(lambda s: "; ".join(sorted(set(s)))))
    return rec.drop(columns=["prio", "abs_len", "k"]).reset_index(drop=True), dups.reset_index(drop=True)


def load(scopus=(), wos=()):
    """read the exports and remove duplicates: (records, duplicates)"""
    parts = [x for x in (read_scopus(scopus), read_wos(wos)) if len(x)]
    if not parts:
        raise FileNotFoundError("no Scopus or Web of Science export given")
    return deduplicate(pd.concat(parts, ignore_index=True))


def query_blocks(query_text, max_blocks=None):
    """concept blocks of a Scopus TITLE-ABS-KEY(...) AND TITLE-ABS-KEY(...) query as compiled regular expressions
    (truncation * becomes word characters), to check which records a query would retrieve"""
    blocks = []
    for b in re.findall(r"TITLE-ABS-KEY\s*\((.*?)\)\s*(?:AND|\n\s*AND|$)", query_text, flags=re.S):
        terms = [x.strip() for x in re.findall(r'"([^"]+)"|(\S+)', b) for x in x if x.strip() and x.strip().upper() not in ("OR", "AND")]
        rx = []
        for term in terms:
            words = [re.escape(w).replace(r"\*", r"\w*") for w in re.split(r"[\s\-]+", term.strip("()")) if w]
            if words:
                rx.append(r"\b" + r"[\s\-]+".join(words) + (r"(?:s|es)?\b" if not words[-1].endswith(r"\w*") else ""))
        if rx:
            blocks.append(re.compile("|".join(rx), re.I))
    return blocks[:max_blocks] if max_blocks else blocks
