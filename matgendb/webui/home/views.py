# Create your views here.

import json
import os

from django.template import RequestContext
from django.shortcuts import render_to_response

from matgendb.query_engine import QueryEngine


qe = None

mgdb_config = os.environ.get("MGDB_CONFIG", "")
if mgdb_config:
    config = json.loads(mgdb_config)
    qe = QueryEngine(host=config["host"], port=config["port"],
                     database=config["database"], user=config["readonly_user"],
                     password=config["readonly_password"],
                     collection=config["collection"],
                     aliases_config=config.get("aliases_config", None))

def index(request):
    if qe is None:
        return "<p>No database configured.</p>"
    d = config.copy()
    d["ndocs"] = qe.collection.count()
    return render_to_response("home/templates/index.html",
                              RequestContext(request, d))
