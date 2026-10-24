"""Command line: rh <command> ... (rh --help for the list)."""
import argparse, json, pathlib, sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rh", description="research-helpers: everyday helpers for reproducible research")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bib", help="verified BibTeX from DOIs (and Zotero)")
    b.add_argument("out"); b.add_argument("refs", nargs="*", help="key=doi pairs or bare DOIs")
    b.add_argument("--dois-file"); b.add_argument("--expect", nargs="*", default=[], help='key="expected title words"')
    b.add_argument("--zotero", nargs="?", const=True, help="offer to Zotero (optionally into this collection)")

    f = sub.add_parser("find-doi", help="Crossref search by title"); f.add_argument("title")
    w = sub.add_parser("author-works", help="works of an author (OpenAlex)")
    w.add_argument("name"); w.add_argument("--institution"); w.add_argument("--since", type=int); w.add_argument("--csv")
    z = sub.add_parser("zotero-push", help="offer queued references to Zotero"); z.add_argument("queue", nargs="?", default="zotero_queue.csv")

    o = sub.add_parser("oa", help="download open-access PDFs for DOIs")
    o.add_argument("dois_file"); o.add_argument("dest"); o.add_argument("--titles"); o.add_argument("--limit", type=int)

    l = sub.add_parser("latex2docx", help="LaTeX to Word through pandoc")
    l.add_argument("main_tex"); l.add_argument("out"); l.add_argument("--csl"); l.add_argument("--numbers", nargs="*", default=[])
    l.add_argument("--margins", default="25,25,25,25", help="left,right,top,bottom in mm")
    l.add_argument("--font", default="Arial"); l.add_argument("--size", type=float, default=12); l.add_argument("--spacing", type=float, default=1.5)
    l.add_argument("--figure-width", default="15cm")
    l.add_argument("--profile", choices=["ieee"], help="publisher template profile: ieee (IEEE conference Word template, two columns)")
    l.add_argument("--reference-docx", help="a publisher's Word template to take the styles from (e.g. IEEE conference-template-a4.docx)")

    r = sub.add_parser("register", help="data register of a folder"); r.add_argument("root"); r.add_argument("--out", default="data_register.csv")
    r.add_argument("--hash-limit-mb", type=float, default=200)
    s = sub.add_parser("scripts", help="reference of scripts from their docstrings"); s.add_argument("root"); s.add_argument("--out", default="pipeline_reference.md")
    s.add_argument("--glob", default="**/*.py")

    q = sub.add_parser("queue", help="run jobs one after another after a condition")
    q.add_argument("jobs_file"); q.add_argument("--log", default="queue.log"); q.add_argument("--after-pid", type=int)
    q.add_argument("--after-file"); q.add_argument("--after-text", default="finished"); q.add_argument("--wait-for-pattern")
    q.add_argument("--keep-awake", action="store_true")
    t = sub.add_parser("template", help="paper templates and citation styles: list, fetch, start a paper")
    t.add_argument("action", choices=["list", "fetch", "new"]); t.add_argument("args", nargs="*")
    t.add_argument("--library", help="library folder (default RH_TEMPLATES or ~/research-templates)")
    a = ap.parse_args(argv)

    if a.cmd == "template":
        from . import templates
        if a.action == "list":
            for r in templates.status(a.library):
                print(f"{r['name']:24} {r['kind']:8} {'yes' if r['in_library'] else 'no ':4} {r['about'][:80]}")
            print("\nstarters (rh template new <starter> <folder>):")
            for k, s in templates.STARTERS.items():
                print(f"  {k:18} {s['about']}")
        elif a.action == "fetch":
            templates.fetch(a.args or None, a.library)
        elif a.action == "new":
            if len(a.args) != 2:
                ap.error("rh template new <starter> <folder>")
            templates.new(a.args[0], a.args[1], a.library)
        return 0

    if a.cmd == "bib":
        from . import bib
        items = list(a.refs)
        if a.dois_file:
            items += [x.strip() for x in pathlib.Path(a.dois_file).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
        if all("=" in x for x in items):
            refs = dict(x.split("=", 1) for x in items)
        else:
            refs = [x.split("=", 1)[-1] for x in items]
        expect = dict(x.split("=", 1) for x in a.expect)
        _, problems = bib.write_bib(a.out, refs, expect=expect, zotero=a.zotero)
        return 1 if problems else 0
    if a.cmd == "find-doi":
        from . import bib
        for d, t, v, y in bib.search_title(a.title):
            print(f"{d} | {t[:90]} | {v[:40]} | {y}")
    if a.cmd == "author-works":
        from . import bib
        rows = bib.author_works(a.name, a.institution, a.since)
        if a.csv:
            import csv
            with open(a.csv, "w", newline="", encoding="utf-8") as fh:
                wr = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["title"]); wr.writeheader(); wr.writerows(rows)
        for x in rows:
            print(f"{x['year']} | {x['type'][:8]} | {(x['title'] or '')[:90]} | {x['doi']} | {x['open_access']}")
    if a.cmd == "zotero-push":
        from . import bib
        bib.push_queue(a.queue)
    if a.cmd == "oa":
        from .open_access import fetch
        dois = [x.strip() for x in pathlib.Path(a.dois_file).read_text(encoding="utf-8").splitlines() if x.strip()]
        titles = {}
        if a.titles:
            import csv
            titles = {r["doi"]: r["title"] for r in csv.DictReader(open(a.titles, encoding="utf-8"))}
        fetch(dois, a.dest, titles, a.limit)
    if a.cmd == "latex2docx":
        from .latex2docx import convert, PageSetup, ieee_profile
        m = [float(x) for x in a.margins.split(",")]
        return convert(a.main_tex, a.out, csl=a.csl, numbers=a.numbers, figure_width=a.figure_width,
                       page=PageSetup(left_mm=m[0], right_mm=m[1], top_mm=m[2], bottom_mm=m[3], font=a.font, size_pt=a.size,
                                      line_spacing=a.spacing), reference_docx=a.reference_docx,
                       profile=ieee_profile(a.reference_docx) if a.profile == "ieee" else None)
    if a.cmd == "register":
        from .records import data_register, write_register
        print(write_register(data_register(a.root, a.hash_limit_mb), a.out))
    if a.cmd == "scripts":
        from .records import script_reference
        root = pathlib.Path(a.root)
        files = sorted(str(p.relative_to(root)) for p in root.glob(a.glob))
        pathlib.Path(a.out).write_text(script_reference(files, root), encoding="utf-8"); print(a.out)
    if a.cmd == "queue":
        from .jobqueue import run_queue, jobs_from_file
        run_queue(jobs_from_file(a.jobs_file), a.log, after_pid=a.after_pid, after_file=a.after_file, after_text=a.after_text,
                  wait_for_pattern=a.wait_for_pattern, keep_awake=a.keep_awake)
    return 0


if __name__ == "__main__":
    sys.exit(main())
