# Research records (`research_helpers.records`)

Research records: a data register and a reference of the scripts of a pipeline, built from what is on disk.

Command line:
    rh register data/ --out records/data_register.csv [--hash-limit-mb 200]
    rh scripts code/ --out records/pipeline_reference.md

Python:
    from research_helpers.records import data_register, script_reference
    reg = data_register("data")                       # list of dicts, one per folder with files
    md = script_reference(["ingest.py", "model.py"], root="code")

Data register: every folder below the root that holds files: number of files, size, row counts of Parquet tables
(if pyarrow is installed), file types, last change, the first lines of a SOURCE.txt in the folder (provenance), and
SHA-256 checksums of files below a size limit. Archive folders (_archive) are skipped. Keeping a SOURCE.txt (where the
data came from, when, under which licence) next to every download makes the register a complete provenance record.

Script reference: for each script, its command, its last git commit and its module docstring (the documentation of
what it reads, does and writes), as Markdown; a script documented in its docstring is documented everywhere.

## Functions and classes


**`data_register(root, hash_limit_mb=200, skip=('_archive', '.git', '__pycache__'))`**




**`script_reference(scripts, root='.', commands=None)`**

scripts: list of paths relative to root (in run order); commands: {script: typical command}


**`sha256(path, chunk=4194304)`**




**`write_register(rows, out)`**


