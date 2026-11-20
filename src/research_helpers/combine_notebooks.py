"""Join numbered percent-format notebook sources (src/NN_*.py) into one connected notebook: a cover, a linked table of
contents, every chapter in order with a numbered heading and an anchor, a "back to contents" link and a pointer to
the next chapter, and the per-notebook setup cells kept only once.

    python -m research_helpers.combine_notebooks <src_dir> <out.py> --title "..." [--intro intro.md]

The output is again a percent-format script, so the project's own build step (convert and execute) turns it into a
single executed .ipynb.
"""
import argparse
import re
from pathlib import Path


def chapters(src):
    """(number, title, text) for each NN_*.py, title from its first '# # ' heading."""
    out = []
    for f in sorted(Path(src).glob("[0-9][0-9]_*.py")):
        t = f.read_text(encoding="utf-8")
        m = re.search(r"^# # (.+)$", t, re.M)
        title = re.sub(r"^\d+\s*·\s*", "", m.group(1).strip()) if m else f.stem
        out.append((f.name[:2], title, t))
    return out


def main():
    """Write the combined script."""
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--title", required=True)
    ap.add_argument("--intro", default=""); a = ap.parse_args()
    ch = chapters(a.src)
    slug = lambda n: f"chapter-{n}"
    toc = "\n".join(f"# {i + 1}. [{t}](#{slug(n)})" for i, (n, t, _) in enumerate(ch))
    intro = Path(a.intro).read_text(encoding="utf-8") if a.intro else ""
    parts = [f"# %% [markdown]\n# # {a.title}\n#\n" + "\n".join("# " + l if l else "#" for l in intro.splitlines()) +
             f"\n#\n# ## <a id=\"contents\"></a>Contents\n#\n{toc}\n#\n# Run the cells from top to bottom; each chapter uses what the chapters before it made.\n"]
    seen_setup = False
    for i, (n, t, text) in enumerate(ch):
        text = re.sub(r"^# # .+$", f'# # <a id="{slug(n)}"></a>Chapter {i + 1}. {t}', text, count=1, flags=re.M)
        if 'if "google.colab" in sys.modules' in text:                        # Colab installer: keep the first only
            if seen_setup:
                text = re.sub(r"# %% \[markdown\]\n# \*Running this in Google Colab\?\*.*?check=True\)\n", "", text, flags=re.S)
            seen_setup = True
        nxt = f" Next: [Chapter {i + 2}. {ch[i + 1][1]}](#{slug(ch[i + 1][0])})." if i + 1 < len(ch) else ""
        parts.append(text.rstrip() + f"\n\n# %% [markdown]\n# [Back to contents](#contents).{nxt}\n")
    Path(a.out).write_text("\n\n".join(parts), encoding="utf-8")
    print(f"{len(ch)} chapters -> {a.out}")


if __name__ == "__main__":
    main()
