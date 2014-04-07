# Create your views here.

import json
import os

from django.template import RequestContext
from django.shortcuts import render_to_response

from matgendb.query_engine import QueryEngine
from matgendb import util as dbutil


qe = None

mgdb_config = os.environ.get("MGDB_CONFIG", "")
if mgdb_config:
    config = json.loads(mgdb_config)
    if not dbutil.normalize_auth(config, readonly_first=True):
        config["user"] = config["password"] = None
    qe = QueryEngine(host=config["host"], port=config["port"],
                     database=config["database"], user=config["user"],
                     password=config["password"],
                     collection=config["collection"],
                     aliases_config=config.get("aliases_config", None))

def index(request):
    if qe is None:
        return "<p>No database configured.</p>"
    d = config.copy()
    d["ndocs"] = qe.collection.count()
    d["keys_list"] = _jsarr(dbutil.collection_keys(qe.collection))
    return render_to_response("home/templates/index.html",
                              RequestContext(request, d))


def _jsarr(x):
    """Return a string that would work for a javascript array"""
    return "[" + ", ".join(['"{}"'.format(i) for i in x]) + "]"