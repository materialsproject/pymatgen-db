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

config = json.loads(os.environ["MGDB_CONFIG"])
qe = QueryEngine(host=config["host"], port=config["port"],
                 database=config["database"], user=config["readonly_user"],
                 password=config["readonly_password"],
                 collection=config["collection"],
                 aliases_config=config.get("aliases_config", None))


def index(request, rest_query):
    if request.method == "GET":
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
            if re.match("^\d+$", critstr):
                criteria = {"task_id": int(critstr)}
            elif re.match("^[\w\(\)]+$", critstr):
                comp = Composition(critstr)
                criteria = {"pretty_formula": comp.reduced_formula}
            elif re.match("^[A-Za-z\-]+$", critstr):
                syms = [Element(sym).symbol
                        for sym in critstr.split("-")]
                syms.sort()
                criteria = {"chemsys": "-".join(syms)}
            else:
                criteria = json.loads(critstr)
            properties = request.POST["properties"]
            if properties == "*":
                properties = None
            else:
                properties = properties.split()
            limit = int(request.POST["limit"])

        except ValueError as ex:
            d = {"valid_response": False,
                 "error_msg": "Bad criteria / properties: {}".format(str(ex))}
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
