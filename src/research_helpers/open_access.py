"""Open-access full texts for a list of DOIs, checked against the paper they should be.

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
"""
import csv, json, os, pathlib, re, shutil, subprocess, tempfile, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; research-helpers open-access retrieval; open-access locations only)"}
MAX_BYTES = 60 * 1024 * 1024


def norm_doi(d):
    d = (d or "").strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d)


def _get(url, timeout=60, accept=None, data=None, extra=None):
    h = dict(UA, **(extra or {}))
    if accept:
        h["Accept"] = accept
    req = urllib.request.Request(url, headers=h, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES + 1), r.headers.get("Content-Type", "")


def openalex(dois):
    """OpenAlex records keyed by normalised DOI (batches of 40, with retries)"""
    out = {}
    for i in range(0, len(dois), 40):
        part = dois[i:i + 40]
        url = ("https://api.openalex.org/works?per-page=50&select=doi,title,open_access,best_oa_location,locations&filter=doi:"
               + "|".join(urllib.parse.quote("https://doi.org/" + d, safe=":/") for d in part))
        for attempt in range(5):
            try:
                data, _ = _get(url, accept="application/json")
                for w in json.loads(data).get("results", []):
                    out[norm_doi(w.get("doi"))] = w
                break
            except Exception:
                time.sleep(5 + 5 * attempt)
        time.sleep(1)
    return out


def semantic_scholar(dois):
    """open-access PDF addresses recorded by Semantic Scholar, keyed by DOI"""
    out = {}
    for i in range(0, len(dois), 400):
        part = [d for d in dois[i:i + 400] if d.startswith("10.")]
        if not part:
            continue
        body = json.dumps({"ids": ["DOI:" + d for d in part]}).encode()
        for attempt in range(4):
            try:
                data, _ = _get("https://api.semanticscholar.org/graph/v1/paper/batch?fields=externalIds,openAccessPdf",
                               timeout=90, data=body, extra={"Content-Type": "application/json"})
                for d, w in zip(part, json.loads(data)):
                    u = ((w or {}).get("openAccessPdf") or {}).get("url")
                    if u:
                        out[d] = u
                break
            except Exception:
                time.sleep(10 + 10 * attempt)
    return out


def pdf_urls(w):
    """open-access PDF addresses of one OpenAlex work, best location first"""
    locs = [w.get("best_oa_location") or {}] + [l for l in (w.get("locations") or []) if l.get("is_oa")]
    urls = []
    for l in locs:
        for u in (l.get("pdf_url"), l.get("landing_page_url")):
            if not u:
                continue
            m = re.search(r"arxiv\.org/abs/([\w.\-/]+)", u)
            if m:
                u = "https://arxiv.org/pdf/" + m.group(1)
            elif u == l.get("landing_page_url"):
                continue
            if u not in urls:
                urls.append(u)
    return urls


def pdf_text(path, first=1, last=3):
    """text of the first pages (pdftotext if available, else pypdf, else empty)"""
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-f", str(first), "-l", str(last), str(path), "-"], capture_output=True, text=True, errors="replace")
        return r.stdout
    try:
        from pypdf import PdfReader
        rd = PdfReader(str(path))
        return " ".join((rd.pages[i].extract_text() or "") for i in range(first - 1, min(last, len(rd.pages))))
    except Exception:
        return ""


def matches(path, doi, title):
    """True if the PDF's first pages contain the DOI or at least 80% of the title's longer words"""
    t = pdf_text(path)
    if not t:
        return None                                              # cannot check
    if doi and doi.lower() in re.sub(r"\s+", "", t).lower():
        return True
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    words = [x for x in norm(title).split() if len(x) > 3]
    head = norm(t[:6000])
    return bool(words) and sum(x in head for x in words) / len(words) >= 0.8


def elsevier_pdf(doi):
    key = os.environ.get("ELSEVIER_API_KEY")
    if not key:
        return None
    h = {"X-ELS-APIKey": key, "Accept": "application/pdf"}
    if os.environ.get("ELSEVIER_INSTTOKEN"):
        h["X-ELS-Insttoken"] = os.environ["ELSEVIER_INSTTOKEN"]
    try:
        data, _ = _get("https://api.elsevier.com/content/article/doi/" + urllib.parse.quote(doi, safe="/"), timeout=90, extra=h)
    except Exception:
        return None
    return data if data.startswith(b"%PDF") and len(data) > 60_000 else None    # a one-page preview is not kept


def fetch(dois, dest, titles=None, limit=None):
    """Download open-access PDFs for `dois` into `dest`. titles: {doi: title} for the check. Returns the log rows."""
    dest = pathlib.Path(dest); (dest / "_unverified").mkdir(parents=True, exist_ok=True)
    titles = {norm_doi(k): v for k, v in (titles or {}).items()}
    log_path = dest / "download_log.csv"
    log = list(csv.DictReader(open(log_path, encoding="utf-8"))) if log_path.exists() else []
    done = {r["doi"] for r in log if r.get("status") == "saved"}
    todo = [d for d in dict.fromkeys(norm_doi(d) for d in dois) if d and d not in done]
    if limit:
        todo = todo[:limit]
    meta, s2 = openalex(todo), semantic_scholar(todo)
    for d in todo:
        w = meta.get(d) or {}
        title = titles.get(d) or w.get("title") or ""
        row = {"doi": d, "title": title, "date": time.strftime("%Y-%m-%d"),
               "oa_status": (w.get("open_access") or {}).get("oa_status", "not in OpenAlex"), "url": "", "file": "", "status": ""}
        urls = pdf_urls(w) if w else []
        if s2.get(d) and s2[d] not in urls:
            urls.append(s2[d])
        ax = re.match(r"(?:arxiv:|10\.48550/arxiv\.)(\d{4}\.\d{4,5})", d)
        if ax:
            urls.insert(0, "https://arxiv.org/pdf/" + ax.group(1))
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", d) + ".pdf"
        if d.startswith("10.1016/"):
            data = elsevier_pdf(d)
            if data:
                (dest / name).write_bytes(data); row.update(status="saved", url="Elsevier API", file=name); urls = []
        if not urls and not row["status"]:
            row["status"] = "no open-access PDF location"
        for u in urls:
            try:
                data, _ = _get(u)
            except Exception as e:
                row.update(status="request failed: " + str(e)[:60], url=u); continue
            if not data.startswith(b"%PDF") or len(data) > MAX_BYTES:
                row.update(status="location did not return a PDF", url=u); continue
            f = dest / name; f.write_bytes(data)
            ok = matches(f, d, title)
            if ok is False:
                f.replace(dest / "_unverified" / name)
                row.update(status="PDF does not match the work (moved to _unverified)", url=u, file="_unverified/" + name); continue
            row.update(status="saved" if ok else "saved (not checked: no PDF text tool)", url=u, file=name); break
        log = [x for x in log if x.get("doi") != d] + [row]
        print(f"{row['status'][:40]:40s} {d}")
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doi", "title", "date", "oa_status", "url", "file", "status"])
        w.writeheader(); w.writerows(log)
    print(f"{sum(r['status'].startswith('saved') for r in log)} saved in {dest} (log: {log_path.name})")
    return log
