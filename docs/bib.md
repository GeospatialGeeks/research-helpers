# Verified references (`research_helpers.bib`)

Verified references: BibTeX from DOIs, title search, an author's works, and a hand-off to Zotero.

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

## Functions and classes


**`author_works(name, institution=None, since=None, limit=200)`**

OpenAlex works of an author (best match of the name, optionally at an institution): list of dicts


**`bibtex(key, doi)`**

cleaned BibTeX entry of a DOI with the given key


**`crossref(doi)`**

Crossref record of a DOI (raises if not found)


**`make_key(m)`**

author-year-word key, e.g. gorelick2017google


**`push_queue(queue_file)`**




**`queue_for_zotero(records, collection, queue_file)`**




**`search_title(title, rows=3)`**

Crossref candidates for a title: list of (doi, title, venue, year)


**`title_matches(m, expected, need=0.6)`**

True if the record's title contains most of the expected words (case and punctuation ignored)


**`title_of(m)`**




**`to_zotero(records, collection=None)`**

records: list of (doi, crossref record). Returns those not delivered (Zotero closed or failure).


**`write_bib(out, refs, expect=None, zotero=None, queue_file=None)`**

refs: {key: doi} or list of DOIs (keys made automatically). expect: {key: expected title words}.
Writes the .bib (archiving an existing one), offers the references to Zotero if `zotero` is given (a collection
name, or True for the selected collection). Returns (written keys, problems).


**`year_of(m)`**




**`zotero_dois()`**

DOIs already in the Zotero library (from a copy of zotero.sqlite, which Zotero keeps locked)


**`zotero_item(m)`**


