# Code inventory (`research_helpers.inventory`)

Inventory of the code across many projects: every function, whether it is documented, and where the same job is done twice.

    python -m research_helpers.inventory ROOT [ROOT ...] --out inventory/

Writes three files to the output folder:

    functions.csv    one row per Python function or JavaScript function: project, file, name, lines, docstring yes/no, topic
    duplicates.csv   functions whose bodies are identical or whose names recur across projects (candidates for one shared copy)
    summary.md       counts per project and per topic, and the share of functions with a docstring

Topics are found from names and bodies with simple keyword rules (TOPICS below), so they are a guide for sorting, not a
classification. Folders that hold copies, environments or build output (SKIP) are left out.

## Functions and classes

**`duplicates(rows)`**

Functions with identical bodies in more than one file, and public names defined in three or more projects.

**`files(roots, exts)`**

Yield source files under the roots, skipping the folders in SKIP.

**`js_functions(path)`**

Yield the same tuple as python_functions for named JavaScript functions (Earth Engine scripts, web pages).

A function counts as documented when a // or /* comment ends on the line just above it.

**`main(argv=None)`**



**`project_of(path, roots)`**

Name a file's project: the first folder below the root it was found under.

**`python_functions(path)`**

Yield (name, first line, last line, has docstring, normalised body) for every function in a Python file.

**`scan(roots)`**

Return one dictionary per function found under the roots.

**`summary(rows, dups)`**

Markdown counts per project and per topic.

**`topic(text)`**

Return the first topic whose keywords appear in text, or 'general'.
