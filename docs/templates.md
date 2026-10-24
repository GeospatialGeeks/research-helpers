# Paper templates and citation styles (`research_helpers.templates`)

A local library of paper templates and citation styles, fetched from their official sources, and new papers started
from them.

Command line:
    rh template list                         what is in the registry and what is already in the library
    rh template fetch [name ...]             download into the library (all downloadable entries if no name)
    rh template new <starter> <folder>       start a paper: main.tex, class and BibTeX style, references.bib, CSL, build notes

Python:
    from research_helpers import templates
    templates.fetch("ieeetran"); templates.new("ieee-conference", "papers/jurse2027")

The library lives in RH_TEMPLATES or ~/research-templates. Each entry is kept as downloaded (archives also unpacked)
with SOURCE.txt: address, date, SHA-256 and licence, so a template can be traced and refreshed. Nothing in the library
is overwritten: a newer download goes alongside, with the date in its folder name.

Some publishers only serve templates to a browser (IEEE's Word templates). Those entries are marked "manual": open the
address, save the files into the folder that `rh template list` shows, and they are used like the others.

## Functions and classes

**`fetch(names=None, lib=None, quiet=False)`**

download registry entries into the library; returns {name: folder}

**`library(path=None)`**



**`new(starter, dest, lib=None)`**

start a paper in dest (which must be empty or new) from a starter template; returns the folder

**`status(lib=None)`**
