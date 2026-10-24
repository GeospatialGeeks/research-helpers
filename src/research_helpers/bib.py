"""Verified references: BibTeX from DOIs, title search, an author's works, and a hand-off to Zotero.

Command line:
    rh bib refs.bib smith2020=10.1000/xyz jones2021=10.1000/abc [--expect "smith2020=Title words"] [--zotero "My collection"]
    rh bib refs.bib --dois-file dois.txt                 one DOI per line; keys are made from author, year and title
    rh find-doi "Title of the paper"                     Crossref search by title (top 3 candidates)
    rh author-works "Firstname Lastname" [--institution "University"]   works of an author (OpenAlex)
    rh zotero-push                                       offer queued references to Zotero again

Python:
    from research_helpers import bib
    rec = bib.crossref("10.1016/j.rse.2017.06.031")       # Crossref record (dict)
    entry = bib.bibtex("gorelick2017", "10.1016/j.rse.2017.06.031")
    bib.write_bib("refs.bib", {"gorelick2017": "10.1016/j.rse.2017.06.031"}, zotero="PhD citations")

Every DOI is resolved on Crossref; the title, venue and year are printed so that a wrong DOI is noticed, and with
--expect the title must match the expected words (a DOI that resolves to another paper is rejected). BibTeX comes from
doi.org content negotiation and is cleaned: the key replaced, HTML entities (&amp;) and dashes converted, month
fields removed, ASCII only (safe for BibTeX 0.99). A .bib that exists is archived first (safeio.keep).

Zotero: references are offered to a running Zotero through its local connector (port 23119, as the browser
Connector does) into the collection named (or the one selected in Zotero), skipping DOIs already in the library
(read from a copy of zotero.sqlite; set the data folder with the environment variable ZOTERO_DATA_DIR). If Zotero is
not running they are queued in zotero_queue.csv (next to the .bib) and offered on the next run or with zotero-push.
Zotero's "Find Available PDFs" then retrieves the full texts that the user has access to.

Only public metadata services are contacted (Crossref, doi.org, OpenAlex); no personal data is sent. Set
RH_MAILTO=you@example.org to use Crossref's polite pool if you wish.
"""
import csv, datetime, difflib, html, json, os, pathlib, re, shutil, sqlite3, tempfile, unicodedata, urllib.parse, urllib.request, uuid

from .safeio import keep

UA = "research-helpers/0.1 (bibliography)" + (f" mailto:{os.environ['RH_MAILTO']}" if os.environ.get("RH_MAILTO") else "")
HDR = {"User-Agent": UA}
CONNECTOR = "http://127.0.0.1:23119/connector/"


def _get(url, accept=None, timeout=60):
    h = dict(HDR)
    if accept:
        h["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read().decode("utf-8")


def crossref(doi):
    """Crossref record of a DOI (raises if not found)"""
    return json.loads(_get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]


def title_of(m):
    return (m.get("title") or [""])[0]


def year_of(m):
    return ((m.get("issued", {}).get("date-parts") or [[None]])[0] or [None])[0]


def title_matches(m, expected, need=0.6):
    """True if the record's title contains most of the expected words (case and punctuation ignored)"""
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
    got, exp = set(norm(title_of(m))), norm(expected)
    if not exp:
        return True
    hit = sum(w in got for w in exp) / len(exp)
    return hit >= need or difflib.SequenceMatcher(None, " ".join(norm(title_of(m))), " ".join(exp)).ratio() >= 0.8


def make_key(m):
    """author-year-word key, e.g. gorelick2017google"""
    fam = ((m.get("author") or [{}])[0].get("family") or "anon")
    fam = re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", fam).encode("ascii", "ignore").decode().lower())
    words = [w for w in re.findall(r"[a-z]+", title_of(m).lower()) if w not in {"a", "an", "the", "of", "on", "in", "for", "and"}]
    return f"{fam}{year_of(m) or ''}{words[0] if words else ''}"


def bibtex(key, doi):
    """cleaned BibTeX entry of a DOI with the given key"""
    b = _get("https://doi.org/" + doi, accept="application/x-bibtex")
    b = re.sub(r"@(\w+)\{[^,]+,", lambda x: f"@{x.group(1)}{{{key},", b, count=1)
    b = html.unescape(b.replace("&amp;", r"\&"))                    # &amp; must become \& for LaTeX
    b = b.replace("–", "--").replace("—", "---").replace("‐", "-").replace("‑", "-")
    b = re.sub(r",\s*month\s*=\s*\{?\w+\}?", "", b)
    return unicodedata.normalize("NFKD", b).encode("ascii", "ignore").decode().strip()


def search_title(title, rows=3):
    """Crossref candidates for a title: list of (doi, title, venue, year)"""
    types = ",".join("type:" + t for t in ("journal-article", "proceedings-article", "book-chapter", "book", "posted-content",
                                           "report", "dataset", "dissertation", "monograph"))     # not peer-review reports
    d = json.loads(_get("https://api.crossref.org/works?rows=%d&filter=%s&query.bibliographic=%s" % (rows + 5, types, urllib.parse.quote(title))))
    items = [i for i in d["message"]["items"] if i.get("type") not in ("peer-review", "component")]
    return [(i.get("DOI"), title_of(i), (i.get("container-title") or [""])[0], year_of(i)) for i in items][:rows]


def author_works(name, institution=None, since=None, limit=200):
    """OpenAlex works of an author (best match of the name, optionally at an institution): list of dicts"""
    a = json.loads(_get("https://api.openalex.org/authors?per-page=10&search=" + urllib.parse.quote(name)))["results"]
    if institution:
        a = [x for x in a if any(institution.lower() in (i["institution"]["display_name"] or "").lower()
                                 for i in x.get("affiliations", []))] or a
    if not a:
        return []
    aid = a[0]["id"].split("/")[-1]
    f = f"author.id:{aid}" + (f",from_publication_date:{since}-01-01" if since else "")
    w = json.loads(_get(f"https://api.openalex.org/works?per-page={min(limit, 200)}&sort=publication_year:desc&filter={f}"))["results"]
    return [{"year": x["publication_year"], "type": x["type"], "title": x["title"], "doi": (x.get("doi") or "").replace("https://doi.org/", ""),
             "venue": ((x.get("primary_location") or {}).get("source") or {}).get("display_name"),
             "authors": "; ".join(y["author"]["display_name"] for y in x["authorships"]), "open_access": x["open_access"]["oa_status"],
             "cited_by": x["cited_by_count"]} for x in w]


# ---------------------------------------------------------------- Zotero
def _zotero_dir():
    return pathlib.Path(os.environ.get("ZOTERO_DATA_DIR", pathlib.Path.home() / "Zotero"))


def zotero_item(m):
    kind = {"journal-article": "journalArticle", "proceedings-article": "conferencePaper", "book-chapter": "bookSection",
            "book": "book", "report": "report", "dataset": "dataset", "posted-content": "preprint"}.get(m.get("type"), "journalArticle")
    date = "-".join(str(p) for p in (m.get("issued", {}).get("date-parts") or [[None]])[0] if p)
    item = {"itemType": kind, "title": title_of(m), "DOI": m.get("DOI", ""), "url": f"https://doi.org/{m.get('DOI', '')}",
            "date": date, "volume": m.get("volume", ""), "issue": m.get("issue", ""), "pages": m.get("page", "").replace("-", "–"),
            "creators": [{"firstName": a.get("given", ""), "lastName": a.get("family", a.get("name", "")), "creatorType": "author"}
                         for a in m.get("author", [])], "attachments": [], "tags": []}
    venue = (m.get("container-title") or [""])[0]
    item["publicationTitle" if kind == "journalArticle" else "proceedingsTitle" if kind == "conferencePaper" else "bookTitle"] = venue
    return item


def zotero_dois():
    """DOIs already in the Zotero library (from a copy of zotero.sqlite, which Zotero keeps locked)"""
    db = _zotero_dir() / "zotero.sqlite"
    if not db.exists():
        return set()
    tmp = pathlib.Path(tempfile.mkdtemp()) / "z.sqlite"
    shutil.copy2(db, tmp)
    con = sqlite3.connect(tmp)
    rows = con.execute("SELECT v.value FROM itemData d JOIN fields f USING(fieldID) JOIN itemDataValues v USING(valueID) "
                       "WHERE f.fieldName='DOI'").fetchall()
    con.close()
    return {r[0].lower() for r in rows}


def _connector(endpoint, payload):
    req = urllib.request.Request(CONNECTOR + endpoint, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def to_zotero(records, collection=None):
    """records: list of (doi, crossref record). Returns those not delivered (Zotero closed or failure)."""
    try:
        _connector("ping", {})
    except Exception:
        return records
    have = zotero_dois()
    todo = [(d, m) for d, m in records if d.lower() not in have]
    target = None
    if collection:
        try:
            _, b = _connector("getSelectedCollection", {})
            target = next((t["id"] for t in json.loads(b).get("targets", []) if t.get("name") == collection), None)
        except Exception:
            pass
    failed = []
    for d, m in todo:
        sid = uuid.uuid4().hex
        try:
            _connector("saveItems", {"sessionID": sid, "uri": f"https://doi.org/{d}", "items": [zotero_item(m)]})
            if target:
                _connector("updateSession", {"sessionID": sid, "target": target})
        except Exception:
            failed.append((d, m))
    print(f"Zotero: {len(records) - len(todo)} already there, {len(todo) - len(failed)} added, {len(failed)} failed")
    return failed


def queue_for_zotero(records, collection, queue_file):
    q = pathlib.Path(queue_file); new = not q.exists()
    with open(q, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "doi", "collection"])
        for d, _ in records:
            w.writerow([datetime.date.today().isoformat(), d, collection or ""])
    print(f"Zotero not running: {len(records)} references queued in {q}")


def push_queue(queue_file):
    q = pathlib.Path(queue_file)
    if not q.exists():
        print("no queue"); return
    rows = list(csv.DictReader(open(q, encoding="utf-8")))
    left = []
    for coll in {r["collection"] for r in rows}:
        recs = [(r["doi"], crossref(r["doi"])) for r in rows if r["collection"] == coll]
        left += [(d, coll) for d, _ in to_zotero(recs, coll or None)]
    keep(q)
    if left:
        with open(q, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["date", "doi", "collection"])
            w.writerows([[datetime.date.today().isoformat(), d, c] for d, c in left])
    print(f"queue: {len(rows) - len(left)} delivered, {len(left)} still queued")


def write_bib(out, refs, expect=None, zotero=None, queue_file=None):
    """refs: {key: doi} or list of DOIs (keys made automatically). expect: {key: expected title words}.
    Writes the .bib (archiving an existing one), offers the references to Zotero if `zotero` is given (a collection
    name, or True for the selected collection). Returns (written keys, problems)."""
    if not isinstance(refs, dict):
        refs = {f"_auto{i}": d for i, d in enumerate(refs)}           # keys made from author, year and title
    entries, records, problems, keys = [], [], [], []
    for key, doi in refs.items():
        try:
            m = crossref(doi)
        except Exception as e:
            problems.append((key, doi, f"not found ({e})")); print("NOT FOUND", key, doi); continue
        if key.startswith("_auto"):
            key = make_key(m)
        if expect and key in expect and not title_matches(m, expect[key]):
            problems.append((key, doi, f"title mismatch: {title_of(m)[:80]}")); print("TITLE MISMATCH", key, doi, "->", title_of(m)[:80]); continue
        entries.append(bibtex(key, doi)); records.append((doi, m)); keys.append(key)
        print("OK", key, "|", title_of(m)[:80], "|", (m.get("container-title") or [""])[0][:40], year_of(m))
    out = pathlib.Path(out)
    keep(out).write_text("\n\n".join(entries) + "\n", encoding="ascii")
    print(f"{len(entries)} of {len(refs)} references -> {out}")
    if zotero:
        coll = zotero if isinstance(zotero, str) else None
        q = queue_file or out.with_name("zotero_queue.csv")
        left = to_zotero(records, coll)
        if left:
            queue_for_zotero(left, coll, q)
    return keys, problems
