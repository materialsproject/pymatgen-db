# Create your views here.

import json
import os
import re

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from pymatgen import Composition, Element

from matgendb.query_engine import QueryEngine
import bson
import datetime

from django.utils.encoding import force_unicode
from django.core.serializers.json import DjangoJSONEncoder

qe = None

mgdb_config = os.environ.get("MGDB_CONFIG", "")
if mgdb_config:
    config = json.loads(mgdb_config)
    qe = QueryEngine(host=config["host"], port=config["port"],
                 database=config["database"], user=config["readonly_user"],
                 password=config["readonly_password"],
                 collection=config["collection"],
                 aliases_config=config.get("aliases_config", None))


def index(request, rest_query):
    if request.method == "GET":
        if qe is None:
            return HttpResponseBadRequest(
                json.dumps({"error": "no database configured"}),
                mimetype="application/json")
        try:
            rest_query = rest_query.strip("/")
            if rest_query == "":
                results = list(qe.query(criteria={}, properties=["task_id"]))
            else:
                toks = rest_query.split("/")
                props = None if len(toks) == 1 else [".".join(toks[1:])]
                results = list(qe.query(criteria={"task_id": int(toks[0])},
                                        properties=props))
            return HttpResponse(json.dumps(results, cls=MongoJSONEncoder),
                                mimetype="application/json")
        except Exception as ex:
            return HttpResponseBadRequest(
                json.dumps({"error": str(ex)}, cls=MongoJSONEncoder),
                mimetype="application/json")


@csrf_exempt
def query(request):
    if request.method == 'POST':
        try:
            critstr = request.POST["criteria"].strip()
            if re.match("^{.*}$", critstr):
                criteria = json.loads(critstr)
            else:
                toks = critstr.split()
                tids = []
                formulas = []
                chemsys = []
                for tok in toks:
                    if re.match("^\d+$", tok):
                        tids.append(int(tok))
                    elif re.match("^[\w\(\)]+$", tok):
                        comp = Composition(tok)
                        formulas.append(comp.reduced_formula)
                    elif re.match("^[A-Za-z\-]+$", tok):
                        syms = [Element(sym).symbol
                                for sym in tok.split("-")]
                        syms.sort()
                        chemsys.append("-".join(syms))
                    else:
                        raise ValueError("{} not understood".format(tok))
                criteria = []
                if tids:
                    criteria.append({"task_id": {"$in": tids}})
                if formulas:
                    criteria.append({"pretty_formula": {"$in": formulas}})
                if chemsys:
                    criteria.append({"chemsys": {"$in": chemsys}})
                criteria = {"$or": criteria} if len(criteria) > 1 else \
                    criteria[0]
            properties = request.POST["properties"]
            if properties == "*":
                properties = None
            else:
                properties = properties.split()
            limit = int(request.POST["limit"])

        except ValueError as ex:
            d = {"valid_response": False,
                 "error": "Bad criteria / properties: {}".format(str(ex))}
            return HttpResponse(
                json.dumps(d), mimetype="application/json")

        results = list(qe.query(criteria=criteria,
                                properties=properties, limit=limit))
        if properties is None and len(results) > 0:
            properties = list(results[0].keys())
        d = {"valid_response": True, "results": results,
             "properties": properties}
        return HttpResponse(json.dumps(d, cls=MongoJSONEncoder),
                            mimetype="application/json")
    return HttpResponseBadRequest(
        json.dumps({"error": "Bad response method. POST should be used."},
                   cls=MongoJSONEncoder),
        mimetype="application/json")


class MongoJSONEncoder(DjangoJSONEncoder):
    """
    Encodes Mongo DB objects into JSON
    In particular is handles BSON Object IDs and Datetime objects
    """

    def default(self, obj):
        if isinstance(obj, bson.objectid.ObjectId):
            return force_unicode(obj)
        elif isinstance(obj, datetime.datetime):
            return str(obj)
        return super(MongoJSONEncoder, self).default(obj)
