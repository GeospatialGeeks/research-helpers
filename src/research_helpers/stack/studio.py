"""Studio: edit every chapter of a document on one page, in LaTeX or in its rendered preview.

    python -m research_helpers.stack studio [<document folder or any .tex in it>] [port]

Without a document it serves a hub of every document under ~/dev at http://127.0.0.1:8770/ (local only).

Every chapter listed in document.toml is shown in order, top to bottom: LaTeX on the left (word-wrapped),
its rendering on the right. Both sides edit the same source:
  * typing in the LaTeX re-renders that chapter after a pause;
  * plain paragraphs and headings in the preview can be edited in place; when you leave the paragraph,
    pandoc turns it back into LaTeX and only that paragraph of the source is replaced. Paragraphs holding
    maths, citations, references, environments or other commands are not editable in the preview (they
    show a dotted outline); double-click them to jump to their source;
  * figures: click one to replace its image or edit its caption; "Add figure" (or dropping an image on
    an editor) saves the image in the document's figures folder and inserts a figure at the cursor.
    Images are never overwritten: a new file gets a new name.
Ctrl+S saves only the changed chapters, and refuses if a file changed on disk since it was opened
(for example in VS Code). Unsaved text is kept in the browser and offered back after a crash.
"Save and publish" rebuilds the document with the repository's own command, commits only what that
changed, and pushes (see publish). The preview is pandoc with MathJax, a quick approximation:
`stack preview` gives the exact PDF.
"""
import fnmatch
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
from html import escape as html_escape
from urllib.parse import parse_qs, unquote, urlparse

from . import load
from .editor import find_document

ROOTS = [Path.home() / "dev"]  # where the hub looks for documents (document.toml)
CM = "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16"
# commands a paragraph may contain and still be edited in the preview (they survive LaTeX -> HTML -> LaTeX)
SAFE = {"emph", "textbf", "textit", "href", "url", "chapter", "section", "subsection", "subsubsection",
        "paragraph", "ldots", "dots", "textendash", "textemdash", "&"}
HEADING = re.compile(r"^(\s*\\(?:chapter|section|subsection|subsubsection|paragraph)\*?)\{((?:[^{}]|\{[^{}]*\})*)\}(.*)$", re.S)
MARK = "STUDIOBLOCK"

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Studio: %TITLE%</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="%CM%/codemirror.min.css"><link rel="stylesheet" href="%CM%/addon/dialog/dialog.min.css">
<script src="%CM%/codemirror.min.js"></script><script src="%CM%/mode/stex/stex.min.js"></script>
<script src="%CM%/addon/dialog/dialog.min.js"></script><script src="%CM%/addon/search/searchcursor.min.js"></script>
<script src="%CM%/addon/search/search.min.js"></script><script src="%CM%/addon/search/jump-to-line.min.js"></script>
<script>window.MathJax={tex:{inlineMath:[["\\(","\\)"]],displayMath:[["\\[","\\]"]]},svg:{fontCache:"global"}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"></script>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1f;--mut:#6b6b70;--line:#e3e0d8;--acc:#0f6e6e;--ed:#ffffff;--kw:#a8457a;--hi:rgba(15,110,110,.10)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#18181a;--fg:#e8e6e1;--mut:#9a9890;--line:#33322f;--acc:#5cc3c3;--ed:#1f1f22;--kw:#e58fbf;--hi:rgba(92,195,195,.12)}}
:root[data-theme="dark"]{--bg:#18181a;--fg:#e8e6e1;--mut:#9a9890;--line:#33322f;--acc:#5cc3c3;--ed:#1f1f22;--kw:#e58fbf;--hi:rgba(92,195,195,.12)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,serif}
header{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:8px 16px;background:var(--bg);border-bottom:1px solid var(--line);font:14px system-ui,sans-serif}
header a{color:inherit}header b{font-size:15px}header .sp{flex:1}#state{color:var(--mut)}
button,select{font:inherit;padding:5px 11px;border:1px solid var(--line);border-radius:6px;background:var(--ed);color:var(--fg);cursor:pointer}
button.primary{background:var(--acc);border-color:var(--acc);color:var(--bg)}
#log{margin:0;max-height:40vh;overflow:auto;padding:8px 16px;font:12px Consolas,monospace;background:var(--line);white-space:pre-wrap}
.layout{display:grid;grid-template-columns:210px 1fr}
nav{position:sticky;top:47px;align-self:start;height:calc(100vh - 47px);overflow:auto;padding:12px;border-right:1px solid var(--line);font:13px system-ui,sans-serif}
nav a{display:block;color:var(--fg);text-decoration:none;padding:3px 4px;border-radius:4px}nav a.sec{padding-left:14px;color:var(--mut)}nav a:hover{background:var(--line)}
nav a.dirty::after{content:" ●";color:#c2410c}nav .wc{color:var(--mut);font-size:11px}
.ch{display:grid;grid-template-columns:1fr 1fr;border-bottom:3px double var(--line)}
.ch .src{border-right:1px solid var(--line);min-width:0}.ch .bar{grid-column:1/-1;display:flex;gap:12px;font:12px system-ui,sans-serif;color:var(--mut);padding:6px 16px;background:var(--line)}
.CodeMirror{height:auto;font:13.5px/1.55 Consolas,monospace;background:var(--ed);color:var(--fg)}.CodeMirror-gutters{background:var(--ed);border:0}
.CodeMirror-linenumber{color:var(--mut)}.cm-s-default .cm-tag{color:var(--acc)}.cm-s-default .cm-keyword{color:var(--kw)}.cm-s-default .cm-comment{color:var(--mut)}
.CodeMirror-cursor{border-color:var(--fg)}.CodeMirror-selected{background:var(--hi)!important}.CodeMirror-dialog{background:var(--ed);color:var(--fg)}
.out{padding:8px 28px 40px;min-width:0;overflow-wrap:anywhere}.out img{max-width:100%;cursor:pointer}.out table{border-collapse:collapse;font-size:14px}
.out td,.out th{border-bottom:1px solid var(--line);padding:3px 8px}.out h1,.out h2,.out h3{line-height:1.25}
.blk{border-radius:4px;padding:1px 4px;margin:0 -4px}.blk[contenteditable="true"]:hover{background:var(--hi)}.blk[contenteditable="true"]:focus{outline:2px solid var(--acc);background:var(--hi)}
.citation:empty::before{content:"[" attr(data-cites) "]";color:var(--mut);font-size:.9em}.tok{background:var(--line);border-radius:3px;padding:0 2px}.tok code{font-size:.85em}.blk.locked:hover{outline:1px dotted var(--mut);cursor:pointer}.blk.flash{background:var(--hi)}
#figmenu{position:absolute;z-index:9;display:none;flex-direction:column;gap:4px;padding:6px;background:var(--ed);border:1px solid var(--line);border-radius:8px;font:13px system-ui;box-shadow:0 4px 18px rgba(0,0,0,.2)}
.drop{outline:3px dashed var(--acc)!important}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{display:none}.ch{grid-template-columns:1fr}}
</style></head><body>
<header><a href="/">All documents</a><b>%TITLE%</b><span id="state">all saved</span><span class="sp"></span>
<label title="highlight the preview paragraph for the line you are on"><input type="checkbox" id="sync" checked> follow cursor</label>
<button id="addfig" title="pick an image; it is saved in the figures folder and a figure is inserted at the cursor">Add figure</button>
<select id="theme" title="theme"><option value="">Auto</option><option value="light">Light</option><option value="dark">Dark</option></select>
<button id="save">Save (Ctrl+S)</button><button id="pub" class="primary" title="save, rebuild this document, commit and push">Save and publish</button></header>
<pre id="log" hidden></pre>
<div class="layout"><nav id="nav"></nav><main id="main"></main></div>
<div id="figmenu"><button data-a="replace">Replace image…</button><button data-a="caption">Edit caption…</button><button data-a="source">Show in LaTeX</button></div>
<input type="file" id="picker" accept="image/*" hidden>
<script>
const chapters = %CHAPTERS%, DOC = %DOCKEY%;
const eds = {}, dirty = new Set(), timers = {}, mtimes = {}, blocks = {};
const $ = s => document.querySelector(s), main = $("#main"), nav = $("#nav"), state = $("#state");
let lastEd = null;
// theme: Auto follows the system; the choice is remembered on this browser only
try { const t = localStorage.getItem("studio-theme") || ""; if (t) document.documentElement.dataset.theme = t; $("#theme").value = t; } catch (e) {}
$("#theme").onchange = e => { const t = e.target.value; if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("studio-theme", t); } catch (e) {} };
const draftKey = n => "studio-draft:" + DOC + ":" + n;
function words(t){ return (t.replace(/%.*$/gm,"").replace(/\\[a-zA-Z]+\*?(\[[^\]]*\])?/g," ").match(/[A-Za-z0-9\u00C0-\u024F\u0600-\u06FF']+/g)||[]).length; }
function setState(){ state.textContent = dirty.size ? dirty.size + " chapter(s) not saved" : "all saved"; document.title = (dirty.size?"● ":"") + "Studio: %TITLE%"; buildNav(); }
async function post(path, body){ return fetch(path, {method:"POST", body: JSON.stringify(body)}); }

async function render(name){
  const out = document.getElementById("out-"+name);
  if (out.contains(document.activeElement)) { timers[name] = setTimeout(()=>render(name), 800); return; } // never redraw under the caret
  const r = await post("render", {name, text: eds[name].getValue()}); const data = await r.json();
  blocks[name] = data; out.innerHTML = "";
  data.forEach((b, i) => {
    const el = document.createElement("div"); el.className = "blk" + (b.editable ? "" : " locked"); el.dataset.i = i; el.innerHTML = b.html;
    if (b.editable) { el.contentEditable = "true"; el.spellcheck = true; el.dataset.orig = el.innerHTML;
      el.addEventListener("blur", () => fromPreview(name, i, el));
      el.addEventListener("keydown", e => { if (e.key === "Escape") { el.innerHTML = el.dataset.orig; el.blur(); } }); }
    else el.ondblclick = () => jumpTo(name, b.start, b.end);
    out.appendChild(el);
  });
  out.querySelectorAll("img").forEach(img => img.onclick = e => figMenu(e, name, +img.closest(".blk").dataset.i));
  if (window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([out]);
  setState();
}
async function fromPreview(name, i, el){ // a paragraph edited in the preview goes back into the LaTeX, alone
  if (el.innerHTML === el.dataset.orig) return;
  const ed = eds[name], b = blocks[name][i];
  const r = await post("tolatex", {name, html: el.innerHTML, source: ed.getValue().slice(b.start, b.end)});
  if (!r.ok) { alert(await r.text()); el.innerHTML = el.dataset.orig; return; }
  const old = ed.getValue().slice(b.start, b.end);
  const latex = old.match(/^\s*/)[0] + await r.text() + old.match(/\s*$/)[0]; el.dataset.orig = el.innerHTML; // keep the spacing around the paragraph
  ed.replaceRange(latex, ed.posFromIndex(b.start), ed.posFromIndex(b.end), "+preview");
}
function jumpTo(name, start, end){
  const ed = eds[name], a = ed.posFromIndex(start); ed.setSelection(a, ed.posFromIndex(Math.min(end, start + 400))); ed.focus();
  window.scrollTo({top: ed.charCoords(a, "page").top - 140, behavior: "smooth"});
}
function blockAt(name, idx){ return (blocks[name]||[]).findIndex(b => idx >= b.start && idx <= b.end); }
function buildNav(){
  nav.innerHTML = "";
  chapters.forEach(c => { const a = document.createElement("a"); a.href = "#ch-"+c.name; a.className = "chap" + (dirty.has(c.name) ? " dirty" : "");
    const h = document.querySelector("#out-"+c.name+" h1"); a.innerHTML = (h ? h.textContent : c.name) + ' <span class="wc">' + words(eds[c.name] ? eds[c.name].getValue() : c.text) + " w</span>";
    nav.appendChild(a);
    document.querySelectorAll("#out-"+c.name+" h2").forEach(h2 => { const s = document.createElement("a"); s.className = "sec"; s.textContent = h2.textContent;
      s.href = "#"; s.onclick = e => { e.preventDefault(); h2.scrollIntoView({behavior:"smooth", block:"center"}); }; nav.appendChild(s); }); });
}
async function save(){
  for (const name of [...dirty]) {
    const r = await post("save", {name, text: eds[name].getValue(), mtime: mtimes[name]});
    if (r.ok) { mtimes[name] = +(await r.text()); dirty.delete(name); try { localStorage.removeItem(draftKey(name)); } catch (e) {} }
    else { alert("Not saved: " + name + "\n" + await r.text()); }
  }
  setState();
}
// figures: replace, caption, add (picker or drag and drop); uploads never overwrite an existing image
let figTarget = null;
function figMenu(e, name, i){ e.stopPropagation(); figTarget = {name, i}; const m = $("#figmenu"); m.style.display = "flex"; m.style.left = e.pageX + "px"; m.style.top = e.pageY + "px"; }
addEventListener("click", () => $("#figmenu").style.display = "none");
async function upload(file){
  const r = await fetch("upload?name=" + encodeURIComponent(file.name), {method:"POST", body: file});
  if (!r.ok) { alert(await r.text()); return null; } return await r.text();
}
function pick(){ return new Promise(res => { const p = $("#picker"); p.value = ""; p.onchange = () => res(p.files[0] || null); p.click(); }); }
function insertFigure(ed, fname){
  const label = fname.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9]+/g, "_");
  ed.replaceSelection("\n\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{" + fname + "}\n\\caption{Caption.}\n\\label{fig:" + label + "}\n\\end{figure}\n");
  ed.focus();
}
$("#figmenu").onclick = async e => {
  const a = e.target.dataset.a; if (!a || !figTarget) return;
  const ed = eds[figTarget.name], b = blocks[figTarget.name][figTarget.i], src = ed.getValue().slice(b.start, b.end);
  let out = src;
  if (a === "source") return jumpTo(figTarget.name, b.start, b.end);
  if (a === "replace") { const f = await pick(); if (!f) return; const n = await upload(f); if (!n) return;
    out = src.replace(/(\\includegraphics(\[[^\]]*\])?\{)[^}]*\}/, (m, p) => p + n + "}"); }
  if (a === "caption") { const m = src.match(/\\caption\{((?:[^{}]|\{[^{}]*\})*)\}/); const c = prompt("Caption (LaTeX)", m ? m[1] : "");
    if (c === null) return; out = m ? src.replace(m[0], "\\caption{" + c + "}") : src.replace(/\\end\{figure\}/, "\\caption{" + c + "}\n\\end{figure}"); }
  ed.replaceRange(out, ed.posFromIndex(b.start), ed.posFromIndex(b.end), "+figure");
};
$("#addfig").onclick = async () => { const ed = lastEd || eds[chapters[0].name]; const f = await pick(); if (!f) return; const n = await upload(f); if (n) insertFigure(ed, n); };

chapters.forEach(c => {
  const box = document.createElement("section"); box.className = "ch"; box.id = "ch-"+c.name;
  box.innerHTML = `<div class="bar"><span>${c.file}</span><span class="sp"></span><span>Ctrl+F find · Alt+G line</span></div><div class="src"></div><div class="out" id="out-${c.name}"></div>`;
  main.appendChild(box); mtimes[c.name] = c.mtime;
  let text = c.text;
  try { const d = localStorage.getItem(draftKey(c.name)); if (d && d !== c.text && confirm("Unsaved changes to " + c.file + " were kept from last time. Restore them?")) { text = d; dirty.add(c.name); } } catch (e) {}
  const ed = CodeMirror(box.querySelector(".src"), {value: text, mode: "stex", lineWrapping: true, lineNumbers: true, viewportMargin: Infinity});
  eds[c.name] = ed;
  ed.on("focus", () => lastEd = ed);
  ed.on("change", () => { dirty.add(c.name); try { localStorage.setItem(draftKey(c.name), ed.getValue()); } catch (e) {}
    clearTimeout(timers[c.name]); timers[c.name] = setTimeout(() => render(c.name), 600); setState(); });
  ed.on("cursorActivity", () => { if (!$("#sync").checked) return;
    const i = blockAt(c.name, ed.indexFromPos(ed.getCursor())); const el = document.querySelector(`#out-${c.name} .blk[data-i="${i}"]`);
    document.querySelectorAll(".blk.flash").forEach(x => x.classList.remove("flash")); if (el) el.classList.add("flash"); });
  const w = ed.getWrapperElement();
  w.addEventListener("dragover", e => { e.preventDefault(); w.classList.add("drop"); });
  w.addEventListener("dragleave", () => w.classList.remove("drop"));
  w.addEventListener("drop", async e => { e.preventDefault(); w.classList.remove("drop"); const f = [...e.dataTransfer.files].find(f => f.type.startsWith("image/"));
    if (!f) return; ed.setCursor(ed.coordsChar({left: e.pageX, top: e.pageY}, "page")); const n = await upload(f); if (n) insertFigure(ed, n); });
  render(c.name);
});
if (location.hash) setTimeout(() => { const e = document.querySelector(location.hash); if (e) e.scrollIntoView(); }, 700);
$("#save").onclick = save;
$("#pub").onclick = async () => {
  await save(); if (dirty.size) return;
  if (!confirm("Rebuild this document, commit and push it to the live site?")) return;
  const log = $("#log"); log.hidden = false; log.textContent = "publishing… (the build takes a minute or two)\n"; state.textContent = "publishing";
  const r = await fetch("publish", {method:"POST", body:"{}"}); log.textContent += await r.text();
  state.textContent = r.ok ? "published: pushed, the site deploys in a minute" : "publish failed: see the log"; log.scrollTop = log.scrollHeight;
};
addEventListener("keydown", e => { if ((e.ctrlKey||e.metaKey) && e.key === "s") { e.preventDefault(); save(); } });
addEventListener("beforeunload", e => { if (dirty.size) { e.preventDefault(); e.returnValue = ""; } });
</script></body></html>"""


def _pandoc(text, src, dst, macros=""):
    r = subprocess.run([shutil.which("pandoc"), "-f", src, "-t", dst, "--wrap=none"] + (["--mathjax"] if dst == "html5" else []),
                       input=(macros + text).encode("utf8"), capture_output=True)
    return r.returncode, r.stdout.decode("utf8"), r.stderr.decode("utf8", "replace")


def split_blocks(text):
    """Paragraph-sized pieces of a chapter with their character offsets: split at blank lines, but never inside
    an environment (a figure or equation with blank lines in it stays one piece)."""
    out, start, depth, pos = [], None, 0, 0
    for line in text.splitlines(keepends=True):
        blank = not line.strip()
        if start is None and not blank:
            start = pos
        depth += len(re.findall(r"\\begin\{", line)) - len(re.findall(r"\\end\{", line))
        pos += len(line)
        if start is not None and depth <= 0 and (blank or pos == len(text)):
            end = pos - (len(line) if blank else 0)
            out.append((start, end))
            start, depth = None, 0
    if start is not None:
        out.append((start, len(text)))
    return out


TOKEN = "STUDIOTOK"
ATOM = re.compile(r"\$[^$]+\$|\\\(.+?\\\)|\\(?!(?:%s)\b)[a-zA-Z]+\*?(?:\[[^\]]*\])*(?:\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*|\\[$%%&#_{}]|~"
                  % "|".join(sorted(SAFE - {"&"})))


def atoms(block):
    """Inline pieces the preview must not touch (maths, citations, references, other commands, ties) become
    tokens; they show as locked chips in the preview and are put back exactly as they were."""
    found = []

    def sub(m):
        found.append(m.group(0))
        return f"{TOKEN}{len(found) - 1}Z"
    return ATOM.sub(sub, block), found


def editable(block):
    if re.search(r"\\begin|\\\[|(?<!\\)%|\\\\", block):
        return False
    m = HEADING.match(block)
    if m and m.group(3).strip() and not re.fullmatch(r"(\s*\\label\{[^{}]*\})+\s*", m.group(3)):
        return False  # a heading run together with text: edit it in the LaTeX
    if m and atoms(m.group(2))[1]:
        return False  # a heading holding commands or maths: edit it in the LaTeX
    text, _ = atoms(block)
    return all(c in SAFE for c in re.findall(r"\\([a-zA-Z]+|&)", text))


class Doc:
    """One document: its chapters, macros, figure folders and the page that edits them."""

    def __init__(self, doc, key):
        d = load(doc)
        self.doc, self.key, self.src = doc, key, d["_src"]
        self.figdir = doc / d.get("figures", "figures")
        self.figs = [self.figdir, self.src]
        self.files = {c: self.src / f"{c}.tex" for c in d.get("chapters", [])}
        self.title = d.get("title", doc.name)
        self.macros = "".join((self.src / (m if m.endswith(".tex") else m + ".tex")).read_text(encoding="utf8") + "\n"
                              for m in d.get("defines", []))

    def page(self):
        chapters = [{"name": c, "file": str(f.relative_to(self.doc.parent)).replace("\\", "/"),
                     "text": f.read_text(encoding="utf8"), "mtime": f.stat().st_mtime} for c, f in self.files.items()]
        return (PAGE.replace("%TITLE%", self.title).replace("%CM%", CM).replace("%DOCKEY%", json.dumps(self.key))
                .replace("%CHAPTERS%", json.dumps(chapters)))

    def render(self, text):
        """Each paragraph rendered in one pandoc call (separated by marker paragraphs), with its offsets."""
        spans = split_blocks(text)
        parts = []
        toks = {}
        for i, (a, b) in enumerate(spans):
            block = text[a:b]
            if editable(block):
                block, toks[i] = atoms(block)
            block = re.sub(r"\\input\{([^}]*)\}", r"\\textit{[input: \1]}", block)
            parts.append(f"{MARK}{i}\n\n{block}\n\n")
        code, html, err = _pandoc("".join(parts), "latex", "html5", self.macros)
        pieces = re.split(rf"<p>{MARK}(\d+)</p>", html)
        found = {int(pieces[k]): pieces[k + 1] for k in range(1, len(pieces) - 1, 2)}
        out = []
        for i, (a, b) in enumerate(spans):
            h = re.sub(r'src="([^"/:]+?)"', r'src="fig/\1"', found.get(i, "")).strip()
            for n, atom in enumerate(toks.get(i, [])):
                if atom.startswith("$"):
                    shown = "\\(" + atom[1:-1] + "\\)"
                elif atom.startswith("\\("):
                    shown = atom
                elif len(atom) == 2 and atom[0] == "\\":
                    shown = html_escape(atom[1])  # \% \& \$ \# \_ show as the character
                else:
                    shown = "&nbsp;" if atom == "~" else f"<code>{html_escape(atom)}</code>"
                h = h.replace(f"{TOKEN}{n}Z", f'<span class="tok" contenteditable="false" data-t="{n}">{shown}</span>', 1)
            if code and i == 0:
                h = f"<pre style='color:#b91c1c'>{err}</pre>" + h
            out.append({"start": a, "end": b, "html": h, "editable": editable(text[a:b]) and bool(h)})
        return out

    def to_latex(self, html, source):
        m = HEADING.match(source)
        if m:  # keep the heading command; only its text changes
            head = re.search(r"<h\d[^>]*>(.*?)</h\d>", html, re.S)
            body = re.sub(r'<span class="tok".*?</span>', "", head.group(1) if head else html, flags=re.S)
            title = " ".join(re.sub(r"<[^>]+>", "", body).split())
            before = " ".join(re.sub(r"<[^>]+>", "", _pandoc(m.group(2), "latex", "html5")[1]).split())
            if title == before:
                return source  # heading text not changed: keep the source exactly
            code, text, err = _pandoc(html_escape(title), "html", "latex")
            return f"{m.group(1)}{{{text.strip()}}}{m.group(3)}"
        _, found = atoms(source)
        html = re.sub(r'<span class="tok"[^>]*data-t="(\d+)"[^>]*>.*?</span>', lambda m: f"{TOKEN}{m.group(1)}Z", html, flags=re.S)
        code, text, err = _pandoc(html, "html", "latex")
        if code:
            raise ValueError(err)
        text = re.sub(rf"{TOKEN}(\d+)Z", lambda m: found[int(m.group(1))], text.strip())
        if TOKEN in text:
            raise ValueError("a locked piece (maths, citation or reference) could not be put back; edit this paragraph in the LaTeX")
        return text

    def upload(self, name, data):
        """Save an image into the figures folder under a name that is not taken yet; return that name."""
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(name).stem).strip("_") or "figure"
        ext = Path(name).suffix.lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf"):
            raise ValueError("images only: png, jpg, svg, gif or pdf")
        self.figdir.mkdir(parents=True, exist_ok=True)
        f, n = self.figdir / f"{stem}{ext}", 2
        while f.exists():
            f, n = self.figdir / f"{stem}_{n}{ext}", n + 1
        f.write_bytes(data)
        print("figure", f, flush=True)
        return f.name

    def figure(self, name):
        for folder in self.figs:
            for f in [folder / name, *folder.glob(name + ".*")]:
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
                    return f


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf8", errors="replace")


def publish(doc):
    """Rebuild one document with its repository's own web command (.stack-web), then commit and push only
    what this rebuild changed plus the document's sources. Refuses when the repository has no .stack-web
    (no public site) or the document matches a pattern in .stack-hold (work held back from publication)."""
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
    chapters = sorted({Path(f).stem for f in files if f.startswith(rel + "/") and f.endswith(".tex")})
    msg = f"Update {doc.name}" + (f": {', '.join(chapters)}" if chapters else " (rebuild)")  # small, plain commit messages
    c = _git(repo, "-c", "user.name=Ahmad Ammar", "-c", "user.email=ahmadammargeo@gmail.com", "commit", "-m", msg)
    pu = _git(repo, "push")
    log += f"committed {len(files)} files\n" + c.stdout[-300:] + pu.stderr[-300:]
    return pu.returncode == 0, log + ("pushed" if pu.returncode == 0 else "push failed")


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


def studio(target=None, port="8770"):
    """With a document (or a file in one): open it. Without: the hub of every document under ~/dev, which stays
    running; /open?file=<path to a .tex> (used by the site's Admin bar) opens that document at that chapter."""
    one = find_document(target) if target else None
    if target and one is None:
        sys.exit(f"no document.toml at or above {target}")
    docs = documents([one])

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
                    return "404", None, u
                key = key_of(doc)
                if key is None:
                    key = doc.name
                    docs[key] = doc
                return "redirect", f"/d/{key}/#ch-{f.stem}", u
            parts = u.path.strip("/").split("/", 2)
            if parts[0] == "d" and len(parts) >= 2 and parts[1] in docs:
                return "doc", (Doc(docs[parts[1]], parts[1]), parts[2] if len(parts) == 3 else ""), u
            return ("index" if u.path == "/" else "404"), None, u

        def do_GET(self):
            kind, arg, u = self._route()
            if kind == "index":
                return self._send(index())
            if kind == "redirect":
                return self._send("", code=302, extra=[("Location", arg)])
            if kind == "doc":
                doc, rest = arg
                if rest == "":
                    return self._send(doc.page())
                if rest.startswith("fig/"):
                    f = doc.figure(Path(unquote(rest[4:])).name)
                    if f:
                        return self._send(f.read_bytes(), mimetypes.guess_type(f.name)[0])
            self._send("not found", "text/plain", 404)

        def do_POST(self):
            kind, arg, u = self._route()
            if kind != "doc":
                return self._send("not found", "text/plain", 404)
            doc, rest = arg
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                if rest == "upload":
                    return self._send(doc.upload(unquote(parse_qs(u.query).get("name", ["figure.png"])[0]), raw), "text/plain")
                if rest == "publish":
                    ok, text = publish(doc.doc)
                    return self._send(text, "text/plain; charset=utf-8", 200 if ok else 500)
                data = json.loads(raw)
                if rest == "tolatex":
                    return self._send(doc.to_latex(data["html"], data["source"]), "text/plain; charset=utf-8")
                f = doc.files.get(data.get("name"))
                if f is None:
                    return self._send("unknown chapter", "text/plain", 400)
                if rest == "render":
                    return self._send(json.dumps(doc.render(data["text"])), "application/json")
                if rest == "save":
                    if data.get("mtime") and abs(f.stat().st_mtime - float(data["mtime"])) > 1e-3:
                        return self._send(f"{f.name} changed on disk since this page opened (another editor?). "
                                          "Copy your text, reload the page, and apply it again.", "text/plain", 409)
                    f.write_text(data["text"], encoding="utf8", newline="\n")
                    print("saved", f, flush=True)
                    return self._send(str(f.stat().st_mtime), "text/plain")
            except (ValueError, KeyError, TypeError) as e:
                return self._send(f"bad request: {e}", "text/plain", 400)
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
