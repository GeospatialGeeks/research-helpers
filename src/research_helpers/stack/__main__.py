"""python -m research_helpers.stack ACTION [ARGS]: run a document action (layouts, pdf, web, check, snapshot,
deploy, skin, editor, preview, doctor, studio).
"""
import sys

from .editor import doctor, editor, preview
from .studio import studio
from . import audit, check, deploy, layouts, pdf, refresh_skin, snapshot, web

action, *args = sys.argv[1:] or ["layouts"]
{"layouts": layouts, "pdf": pdf, "web": web, "check": check, "snapshot": snapshot, "deploy": deploy, "skin": refresh_skin, "editor": editor, "preview": preview, "studio": studio, "doctor": doctor, "audit": audit}[action](*args)
