import sys

from . import check, deploy, layouts, pdf, refresh_skin, snapshot, web

action, *args = sys.argv[1:] or ["layouts"]
{"layouts": layouts, "pdf": pdf, "web": web, "check": check, "snapshot": snapshot, "deploy": deploy, "skin": refresh_skin}[action](*args)
