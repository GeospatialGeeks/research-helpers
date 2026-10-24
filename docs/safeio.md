# Never overwrite (`research_helpers.safeio`)

Safe writing: an existing file is never overwritten.

    from research_helpers.safeio import keep
    df.to_csv(keep("results/table.csv"), index=False)

keep(path) moves an existing file of that name into <folder>/_archive/<run time>/ and returns the path, now free to
write. Every earlier version stays on disk; one archive folder is used per run of a program. Use it for every derived
output; original data (downloads, raw exports) should not be written by code at all.

## Functions and classes

**`keep(path, archive='_archive')`**

Archive an existing file at `path` and return `path` as a pathlib.Path.
