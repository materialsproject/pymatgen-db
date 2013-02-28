# Create your views here.

import json

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import os
from matgendb.query_engine import QueryEngine
from pymatgen import Composition

def index(request):
    return render_to_response("home/templates/index.html",
                              RequestContext(request, {}))

@csrf_exempt
def query(request):
    if request.method == 'POST':
        try:
            critstr = request.POST["criteria"]
            try:
                criteria = {"pretty_formula": Composition(critstr).reduced_formula}
            except:
                try:
                    criteria = {"task_id": int(critstr)}
                except ValueError:
                    criteria = json.loads(critstr)
            properties = request.POST["properties"].split()
        except ValueError:
            d = {"valid_response": False,
                 "error_msg": "Bad criteria or properties."}
            return HttpResponse(
                json.dumps(d), mimetype="application/json")

        d = json.loads(os.environ["MGDB_CONFIG"])
        qe = QueryEngine(host=d["host"], port=d["port"],
                         database=d["database"], user=d["readonly_user"],
                         password=d["readonly_password"],
                         collection=d["collection"])
        results = list(qe.query(criteria=criteria,
                                properties=properties))
        d = {"valid_response": True, "results": results,
             "properties": properties}
        return HttpResponse(json.dumps(d),
                            mimetype="application/json")
