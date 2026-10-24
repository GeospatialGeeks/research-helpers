"""Safe writing: an existing file is never overwritten.

    from research_helpers.safeio import keep
    df.to_csv(keep("results/table.csv"), index=False)

keep(path) moves an existing file of that name into <folder>/_archive/<run time>/ and returns the path, now free to
write. Every earlier version stays on disk; one archive folder is used per run of a program. Use it for every derived
output; original data (downloads, raw exports) should not be written by code at all.
"""
import datetime
import pathlib
import shutil

_RUN = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def keep(path, archive="_archive"):
    """Archive an existing file at `path` and return `path` as a pathlib.Path."""
    p = pathlib.Path(path)
    if p.exists():
        dest = p.parent / archive / _RUN / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while dest.exists():
            dest = dest.with_name(f"{p.stem}__{n}{p.suffix}")
            n += 1
        shutil.move(str(p), str(dest))
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p
