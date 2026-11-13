"""Studio: edit every chapter of a document on one page, each beside its rendered preview.

    python -m research_helpers.stack studio <document folder or any .tex in it> [port]

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
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
<header><b>%TITLE%</b><span id="state">all saved</span><span class="sp"></span>
<label><input type="checkbox" id="sync" checked> scroll preview with source</label>
<button id="save">Save (Ctrl+S)</button></header>
<div class="layout"><nav id="nav"></nav><main id="main"></main></div>
<script>
const chapters = %CHAPTERS%;
const eds = {}, dirty = new Set(), timers = {};
const main = document.getElementById("main"), nav = document.getElementById("nav"), state = document.getElementById("state");
function setState(){ state.textContent = dirty.size ? dirty.size + " chapter(s) not saved" : "all saved"; document.title = (dirty.size?"● ":"") + "Studio: %TITLE%";
  document.querySelectorAll("nav a.chap").forEach(a=>a.classList.toggle("dirty", dirty.has(a.dataset.c))); }
async function render(name){
  const r = await fetch("/render", {method:"POST", body: JSON.stringify({name, text: eds[name].getValue()})});
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
    const r = await fetch("/save", {method:"POST", body: JSON.stringify({name, text: eds[name].getValue()})});
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
document.getElementById("save").onclick = save;
addEventListener("keydown", e=>{ if ((e.ctrlKey||e.metaKey) && e.key==="s") { e.preventDefault(); save(); } });
addEventListener("beforeunload", e=>{ if (dirty.size) { e.preventDefault(); e.returnValue=""; } });
</script></body></html>"""


def studio(target=".", port="8770"):
    doc = find_document(target)
    if doc is None:
        sys.exit(f"no document.toml at or above {target}")
    d = load(doc)
    src = d["_src"]
    figs = [doc / d.get("figures", "figures"), src]
    files = {c: src / f"{c}.tex" for c in d.get("chapters", [])}
    if not files:
        sys.exit("document.toml lists no chapters")
    macros = "".join((src / (m if m.endswith(".tex") else m + ".tex")).read_text(encoding="utf8") + "\n"
                     for m in d.get("defines", []))
    pandoc = shutil.which("pandoc")

    def render(text):
        # \input'd generated tables or snippets are shown as a note; figures point at /fig/
        text = re.sub(r"\\input\{([^}]*)\}", r"\\textit{[input: \1]}", text)
        r = subprocess.run([pandoc, "-f", "latex", "-t", "html5", "--mathjax", "--wrap=none"],
                           input=(macros + text).encode("utf8"), capture_output=True)
        html = r.stdout.decode("utf8")
        html = re.sub(r'src="([^"/:]+?)"', r'src="/fig/\1"', html)
        if r.returncode:
            html = f"<pre style='color:#b91c1c'>{r.stderr.decode('utf8', 'replace')}</pre>" + html
        return html

    page = (PAGE.replace("%TITLE%", d.get("title", doc.name))
            .replace("%CHAPTERS%", json.dumps([{"name": c, "file": str(f.relative_to(doc.parent)).replace("\\", "/"),
                                                "text": f.read_text(encoding="utf8")} for c, f in files.items()])))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, kind="text/html; charset=utf-8", code=200):
            b = body if isinstance(body, bytes) else body.encode("utf8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/":
                return self._send(page)
            if self.path.startswith("/fig/"):
                name = Path(self.path[5:]).name
                for folder in figs:
                    for f in [folder / name, *folder.glob(name + ".*")]:
                        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
                            return self._send(f.read_bytes(), mimetypes.guess_type(f.name)[0])
            self._send("not found", "text/plain", 404)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            f = files.get(data.get("name"))
            if f is None:
                return self._send("unknown chapter", "text/plain", 400)
            if self.path == "/render":
                return self._send(render(data["text"]))
            if self.path == "/save":
                f.write_text(data["text"], encoding="utf8", newline="\n")
                print("saved", f, flush=True)
                return self._send("ok", "text/plain")
            self._send("not found", "text/plain", 404)

    server = ThreadingHTTPServer(("127.0.0.1", int(port)), H)
    url = f"http://127.0.0.1:{port}/"
    print("studio for", doc, "at", url, "(Ctrl+C to stop)", flush=True)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()
