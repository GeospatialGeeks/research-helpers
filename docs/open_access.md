# Open-access full texts (`research_helpers.open_access`)

Open-access full texts for a list of DOIs, checked against the paper they should be.

Command line:
    rh oa dois.txt pdfs/ [--titles titles.csv] [--limit 50]
        dois.txt: one DOI per line; titles.csv (optional): doi,title for the check of each PDF

Python:
    from research_helpers.open_access import fetch
    log = fetch(["10.1038/s41467-020-18321-y"], "pdfs/")

For every DOI the open-access locations are looked up in OpenAlex and Semantic Scholar (no account needed); arXiv
identifiers are mapped to their PDF address; for Elsevier DOIs the publisher's text-and-data-mining API is used if
ELSEVIER_API_KEY (and optionally ELSEVIER_INSTTOKEN) is set in the environment. Only open-access locations are tried;
nothing behind a paywall is requested. A downloaded file is kept only if it is a PDF whose first pages contain the
DOI or most words of the title (checked with pdftotext from Poppler, or pypdf if installed); otherwise it is moved to
<dest>/_unverified/. Every attempt is written to <dest>/download_log.csv, so a run can be repeated and audited;
DOIs saved before are skipped.

## Functions and classes

**`elsevier_pdf(doi)`**



**`fetch(dois, dest, titles=None, limit=None)`**

Download open-access PDFs for `dois` into `dest`. titles: {doi: title} for the check. Returns the log rows.

**`matches(path, doi, title)`**

True if the PDF's first pages contain the DOI or at least 80% of the title's longer words

**`norm_doi(d)`**



**`openalex(dois)`**

OpenAlex records keyed by normalised DOI (batches of 40, with retries)

**`pdf_text(path, first=1, last=3)`**

text of the first pages (pdftotext if available, else pypdf, else empty)

**`pdf_urls(w)`**

open-access PDF addresses of one OpenAlex work, best location first

**`semantic_scholar(dois)`**

open-access PDF addresses recorded by Semantic Scholar, keyed by DOI
