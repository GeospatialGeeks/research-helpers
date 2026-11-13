"""Studio: edit every chapter of a document on one page, each beside its rendered preview.

    python -m research_helpers.stack studio [<document folder or any .tex in it>] [port]

Without a document it serves a hub of every document under ~/dev at http://127.0.0.1:8770/.

Opens http://127.0.0.1:<port> (local only). Every chapter listed in document.toml is shown in order,
top to bottom, as an editor (word-wrapped) with its rendering beside it, so you read and edit the
whole document as one scroll, as on the web version. Typing re-renders that chapter after a pause;
Ctrl+S (or the Save button) writes the changed chapters back to their .tex files. Double-click a
paragraph in a preview to jump to its source. The rendering is pandoc with MathJax, a quick
approximation of the PDF: run `stack preview` for the exact PDF and the build for the web pages.
Files are only written when you save, and only the chapters you changed.
"""
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import load
from .editor import find_document

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Studio: %TITLE%</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/stex/stex.min.js"></script>
<script>window.MathJax={tex:{inlineMath:[["\\(","\\)"]],displayMath:[["\\[","\\]"]]},svg:{fontCache:"global"}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"></script>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1f;--mut:#6b6b70;--line:#e3e0d8;--acc:#0f6e6e;--ed:#ffffff}
@media (prefers-color-scheme:dark){:root{--bg:#18181a;--fg:#e8e6e1;--mut:#9a9890;--line:#33322f;--acc:#5cc3c3;--ed:#1f1f22}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,serif}
header{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;padding:8px 16px;background:var(--bg);border-bottom:1px solid var(--line);font:14px system-ui,sans-serif}
header b{font-size:15px}header .sp{flex:1}button{font:inherit;padding:5px 12px;border:1px solid var(--line);border-radius:6px;background:var(--ed);color:var(--fg);cursor:pointer}
#state{color:var(--mut)}.layout{display:grid;grid-template-columns:200px 1fr;gap:0}
nav{position:sticky;top:45px;align-self:start;height:calc(100vh - 45px);overflow:auto;padding:12px;border-right:1px solid var(--line);font:13px system-ui,sans-serif}
nav a{display:block;color:var(--fg);text-decoration:none;padding:3px 4px;border-radius:4px}nav a.sec{padding-left:14px;color:var(--mut)}nav a:hover{background:var(--line)}
nav a.dirty::after{content:" ●";color:#c2410c}
.ch{display:grid;grid-template-columns:1fr 1fr;border-bottom:3px double var(--line)}
.ch .src{border-right:1px solid var(--line);min-width:0}.ch .bar{grid-column:1/-1;font:12px system-ui,sans-serif;color:var(--mut);padding:6px 16px;background:var(--line)}
.CodeMirror{height:auto;font:13.5px/1.5 Consolas,monospace;background:var(--ed);color:var(--fg)}.CodeMirror-gutters{background:var(--ed);border:0}
.cm-s-default .cm-tag{color:var(--acc)}.cm-s-default .cm-keyword{color:#a8457a}.CodeMirror-cursor{border-color:var(--fg)}
.out{padding:8px 28px 40px;min-width:0;overflow-wrap:anywhere}.out img{max-width:100%}.out table{border-collapse:collapse;font-size:14px}.out td,.out th{border-bottom:1px solid var(--line);padding:3px 8px}
.out h1,.out h2,.out h3{line-height:1.25}.out p:hover{outline:1px dashed var(--line);cursor:pointer}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{display:none}.ch{grid-template-columns:1fr}}
</style></head><body>
<header><a href="/" style="color:inherit">All documents</a> <b>%TITLE%</b><span id="state">all saved</span><span class="sp"></span>
<label><input type="checkbox" id="sync" checked> scroll preview with source</label>
<button id="save">Save (Ctrl+S)</button> <button id="pub" title="save, rebuild this document, commit and push">Save and publish</button></header>
<pre id="log" hidden style="margin:0;max-height:40vh;overflow:auto;padding:8px 16px;font:12px Consolas,monospace;background:var(--line)"></pre>
<div class="layout"><nav id="nav"></nav><main id="main"></main></div>
<script>
const chapters = %CHAPTERS%;
const eds = {}, dirty = new Set(), timers = {};
const main = document.getElementById("main"), nav = document.getElementById("nav"), state = document.getElementById("state");
function setState(){ state.textContent = dirty.size ? dirty.size + " chapter(s) not saved" : "all saved"; document.title = (dirty.size?"● ":"") + "Studio: %TITLE%";
  document.querySelectorAll("nav a.chap").forEach(a=>a.classList.toggle("dirty", dirty.has(a.dataset.c))); }
async function render(name){
  const r = await fetch("render", {method:"POST", body: JSON.stringify({name, text: eds[name].getValue()})});
  const out = document.getElementById("out-"+name); out.innerHTML = await r.text();
  if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([out]);
  out.querySelectorAll("p,li,h1,h2,h3,h4").forEach(el=>el.ondblclick=()=>jump(name, el.textContent));
  buildNav();
}
function jump(name, text){ // find the paragraph's opening words in the source and select them
  const ed = eds[name], src = ed.getValue(), words = text.trim().split(/\s+/).slice(0,5);
  for (let n = words.length; n > 0; n--) { const w = words.slice(0,n).join(" ");
    const i = src.indexOf(w); if (i >= 0) { const a = ed.posFromIndex(i);
      ed.setSelection(a, ed.posFromIndex(i + w.length)); ed.focus();
      ed.getWrapperElement().closest(".ch").scrollIntoView({block:"nearest"});
      const y = ed.charCoords(a, "page").top; window.scrollTo({top: y - 120, behavior:"smooth"}); return; } }
}
function buildNav(){
  nav.innerHTML = "";
  chapters.forEach(c=>{ const a = document.createElement("a"); a.href="#ch-"+c.name; a.className="chap"; a.dataset.c=c.name;
    a.textContent = (document.querySelector("#out-"+c.name+" h1")||{}).textContent || c.name; nav.appendChild(a);
    document.querySelectorAll("#out-"+c.name+" h2").forEach(h=>{ const s=document.createElement("a"); s.className="sec"; s.textContent=h.textContent;
      s.href="#"; s.onclick=e=>{e.preventDefault(); h.scrollIntoView({behavior:"smooth"});}; nav.appendChild(s); }); });
  setState();
}
async function save(){
  for (const name of [...dirty]) {
    const r = await fetch("save", {method:"POST", body: JSON.stringify({name, text: eds[name].getValue()})});
    if (r.ok) dirty.delete(name); else alert("could not save " + name + ": " + await r.text());
  }
  setState();
}
chapters.forEach(c=>{
  const box = document.createElement("section"); box.className="ch"; box.id="ch-"+c.name;
  box.innerHTML = `<div class="bar">${c.file}</div><div class="src"></div><div class="out" id="out-${c.name}"></div>`;
  main.appendChild(box);
  const ed = CodeMirror(box.querySelector(".src"), {value: c.text, mode:"stex", lineWrapping:true, lineNumbers:true, viewportMargin:Infinity});
  eds[c.name] = ed;
  ed.on("change", ()=>{ dirty.add(c.name); setState(); clearTimeout(timers[c.name]); timers[c.name] = setTimeout(()=>render(c.name), 700); });
  ed.on("cursorActivity", ()=>{ if (!document.getElementById("sync").checked) return; // keep the preview level with the line being edited
    const out = document.getElementById("out-"+c.name), frac = ed.getCursor().line / Math.max(1, ed.lineCount()-1);
    const els = out.querySelectorAll("p,h1,h2,h3,figure,table,ul,ol"); const el = els[Math.round(frac*(els.length-1))];
    if (el) { document.querySelectorAll(".out .here").forEach(x=>x.classList.remove("here")); el.style.background="rgba(15,110,110,.08)"; setTimeout(()=>el.style.background="",900); } });
  render(c.name);
});
if (location.hash) setTimeout(()=>{const e=document.querySelector(location.hash); if(e) e.scrollIntoView();}, 600);
document.getElementById("save").onclick = save;
document.getElementById("pub").onclick = async ()=>{
  await save(); if (dirty.size) return;
  if (!confirm("Rebuild this document, commit and push it to the live site?")) return;
  const log = document.getElementById("log"); log.hidden = false; log.textContent = "publishing… (the build takes a minute or two)\n"; state.textContent = "publishing";
  const r = await fetch("publish", {method:"POST", body:"{}"}); log.textContent += await r.text();
  state.textContent = r.ok ? "published: commit pushed, the site deploys in a minute" : "publish failed: see the log"; log.scrollTop = log.scrollHeight;
};
addEventListener("keydown", e=>{ if ((e.ctrlKey||e.metaKey) && e.key==="s") { e.preventDefault(); save(); } });
addEventListener("beforeunload", e=>{ if (dirty.size) { e.preventDefault(); e.returnValue=""; } });
</script></body></html>"""


ROOTS = [Path.home() / "dev"]  # where the hub looks for documents (document.toml)


class Doc:
    """One document: its chapters, macros, figure folders and the page that edits them."""

    def __init__(self, doc):
        d = load(doc)
        self.doc, self.src = doc, d["_src"]
        self.figs = [doc / d.get("figures", "figures"), self.src]
        self.files = {c: self.src / f"{c}.tex" for c in d.get("chapters", [])}
        self.title = d.get("title", doc.name)
        self.macros = "".join((self.src / (m if m.endswith(".tex") else m + ".tex")).read_text(encoding="utf8") + "\n"
                              for m in d.get("defines", []))

    def page(self):
        chapters = [{"name": c, "file": str(f.relative_to(self.doc.parent)).replace("\\", "/"),
                     "text": f.read_text(encoding="utf8")} for c, f in self.files.items()]
        return PAGE.replace("%TITLE%", self.title).replace("%CHAPTERS%", json.dumps(chapters))

    def render(self, text):
        # \input'd generated tables or snippets are shown as a note; figures point at fig/ under this document
        text = re.sub(r"\\input\{([^}]*)\}", r"\\textit{[input: \1]}", text)
        r = subprocess.run([shutil.which("pandoc"), "-f", "latex", "-t", "html5", "--mathjax", "--wrap=none"],
                           input=(self.macros + text).encode("utf8"), capture_output=True)
        html = re.sub(r'src="([^"/:]+?)"', r'src="fig/\1"', r.stdout.decode("utf8"))
        if r.returncode:
            html = f"<pre style='color:#b91c1c'>{r.stderr.decode('utf8', 'replace')}</pre>" + html
        return html

    def figure(self, name):
        for folder in self.figs:
            for f in [folder / name, *folder.glob(name + ".*")]:
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
                    return f


def documents(extra=()):
    found = {}
    for root in ROOTS:
        for t in root.rglob("document.toml") if root.exists() else []:
            if any(p in ("build", "node_modules", ".git") for p in t.relative_to(root).parts):
                continue
            found[t.parent.relative_to(root).as_posix().replace("/", "~")] = t.parent
    for doc in extra:
        if doc and not any(v.resolve() == Path(doc).resolve() for v in found.values()):
            found[Path(doc).name] = Path(doc)
    return found


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf8", errors="replace")


def publish(doc):
    """Rebuild one document with its repository's own web command (.stack-web), then commit and push only
    what this rebuild changed plus the document's sources. Refuses when the repository has no .stack-web
    (no public site) or the document matches a pattern in .stack-hold (work held back from publication)."""
    import fnmatch
    repo = next((p for p in [doc, *doc.parents] if (p / ".git").exists()), None)
    if repo is None or not (repo / ".stack-web").exists():
        return False, "not published: this repository has no .stack-web, so it has no public site to update"
    rel = doc.resolve().relative_to(repo.resolve()).as_posix()
    hold = (repo / ".stack-hold").read_text(encoding="utf8").split() if (repo / ".stack-hold").exists() else []
    if any(fnmatch.fnmatch(rel, h) for h in hold):
        return False, f"not published: {rel} is held back in .stack-hold"
    def changed():
        return {l[3:].strip('"') for l in _git(repo, "status", "--porcelain", "-uall").stdout.splitlines()}
    before = changed()
    cmd = (repo / ".stack-web").read_text(encoding="utf8").strip().format(name=doc.name, path=doc)
    args = cmd.split()
    if args[0] == "python":
        args[0] = sys.executable
    b = subprocess.run(args, cwd=repo, capture_output=True, text=True, encoding="utf8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf8"})
    log = "$ " + cmd + "\n" + "\n".join((b.stdout + b.stderr).splitlines()[-15:]) + "\n"
    if b.returncode:
        return False, log + "build failed: nothing committed"
    files = sorted((changed() - before) | {f for f in changed() if f.startswith(rel + "/") and "/build/" not in f})
    files = [f for f in files if not any(fnmatch.fnmatch(f, h) or f.startswith(h.rstrip("*")) for h in hold)]
    if not files:
        return True, log + "nothing changed: no commit"
    _git(repo, "add", "--", *files)
    c = _git(repo, "-c", "user.name=Ahmad Ammar", "-c", "user.email=ahmadammargeo@gmail.com", "commit", "-m", f"Update {doc.name}")
    pu = _git(repo, "push")
    log += f"committed {len(files)} files\n" + c.stdout[-300:] + pu.stderr[-300:]
    return pu.returncode == 0, log + ("pushed" if pu.returncode == 0 else "push failed")


def studio(target=None, port="8770"):
    """With a document (or a file in one): open it. Without: the hub of every document under ~/dev, which stays
    running; /open?file=<path to a .tex> (used by the site's Admin bar) opens that document at that chapter."""
    one = find_document(target) if target else None
    if target and one is None:
        sys.exit(f"no document.toml at or above {target}")
    docs = documents([one])
    loaded = {}

    def key_of(doc):
        return next((k for k, v in docs.items() if doc and v.resolve() == Path(doc).resolve()), None)

    def index():
        rows = "".join(f'<li><a href="/d/{k}/">{k.replace("~", " / ")}</a></li>' for k in sorted(docs))
        return ("<!doctype html><meta charset=utf-8><title>Studio</title><style>body{font:16px/1.6 system-ui;margin:40px auto;max-width:760px;"
                "padding:0 16px;background:#fbfaf7;color:#1d1d1f}@media(prefers-color-scheme:dark){body{background:#18181a;color:#e8e6e1}a{color:#5cc3c3}}"
                f"</style><h1>Studio</h1><p>{len(docs)} documents with a document.toml.</p><ul>{rows}</ul>")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, kind="text/html; charset=utf-8", code=200, extra=()):
            b = body if isinstance(body, bytes) else body.encode("utf8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(b)

        def _route(self):
            u = urlparse(self.path)
            if u.path == "/open":
                f = Path(unquote(parse_qs(u.query).get("file", [""])[0]))
                doc = find_document(f)
                if doc is None:
                    return "404", None
                key = key_of(doc)
                if key is None:
                    key = doc.name
                    docs[key] = doc
                return "redirect", f"/d/{key}/#ch-{f.stem}"
            parts = u.path.strip("/").split("/", 2)
            if parts[0] == "d" and len(parts) >= 2 and parts[1] in docs:
                if parts[1] not in loaded:
                    loaded[parts[1]] = Doc(docs[parts[1]])
                return "doc", (loaded[parts[1]], parts[2] if len(parts) == 3 else "")
            return ("index", None) if u.path == "/" else ("404", None)

        def do_GET(self):
            kind, arg = self._route()
            if kind == "index":
                return self._send(index())
            if kind == "redirect":
                return self._send("", code=302, extra=[("Location", arg)])
            if kind == "doc":
                doc, rest = arg
                if rest == "":
                    loaded.pop(self.path.strip("/").split("/")[1], None)  # re-read files on every open
                    return self._send(Doc(doc.doc).page())
                if rest.startswith("fig/"):
                    f = doc.figure(Path(rest[4:]).name)
                    if f:
                        return self._send(f.read_bytes(), mimetypes.guess_type(f.name)[0])
            self._send("not found", "text/plain", 404)

        def do_POST(self):
            kind, arg = self._route()
            if kind != "doc":
                return self._send("not found", "text/plain", 404)
            doc, rest = arg
            try:
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            except (ValueError, TypeError):
                return self._send("bad request", "text/plain", 400)
            if rest == "publish":
                ok, text = publish(doc.doc)
                return self._send(text, "text/plain; charset=utf-8", 200 if ok else 500)
            f = doc.files.get(data.get("name"))
            if f is None:
                return self._send("unknown chapter", "text/plain", 400)
            if rest == "render":
                return self._send(doc.render(data["text"]))
            if rest == "save":
                f.write_text(data["text"], encoding="utf8", newline="\n")
                print("saved", f, flush=True)
                return self._send("ok", "text/plain")
            self._send("not found", "text/plain", 404)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", int(port)), H)
    except OSError:  # the hub is already running: just open the page
        server = None
    key = key_of(one)
    url = f"http://127.0.0.1:{port}/" + (f"d/{key}/" if key else "")
    if os.environ.get("RH_NO_BROWSER") != "1":
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    if server:
        print("studio at", url, f"({len(docs)} documents; Ctrl+C to stop)", flush=True)
        server.serve_forever()
