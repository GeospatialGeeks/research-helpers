import sys

from . import check, deploy, layouts, pdf, snapshot, web

action, *args = sys.argv[1:] or ["layouts"]
{"layouts": layouts, "pdf": pdf, "web": web, "check": check, "snapshot": snapshot, "deploy": deploy}[action](*args)
