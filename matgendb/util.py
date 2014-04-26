"""
Utility functions used across scripts
"""
__author__ = "Shyue Ping Ong, Dan Gunter"
__copyright__ = "Copyright 2012-2014, The Materials Project"
__version__ = "1.1"
__maintainer__ = "Dan Gunter"
__email__ = "dkgunter@lbl.gov"
__date__ = "2012-12-01"

## Imports

import bson
import datetime
import json
import logging
from pymongo.mongo_client import MongoClient

from matgendb.dbconfig import DBConfig

# Temporarily allow normalize_auth to be imported
# from this module (as well as new location).
# --dang 2014-04-25
from matgendb.dbconfig import normalize_auth

## Logging

_log = logging.getLogger("mg.util")

## Classes

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bson.objectid.ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


## Functions

def get_settings(config_file):
    cfg = DBConfig(config_file)
    return cfg.settings

def get_database(config_file=None, settings=None, admin=False):
    d = get_settings(config_file) if settings is None else settings
    conn = MongoClient(host=d["host"], port=d["port"])
    db = conn[d["database"]]
    try:
        user = d["admin_user"] if admin else d["readonly_user"]
        passwd = d["admin_password"] if admin else d["readonly_password"]
        db.authenticate(user, passwd)
    except KeyError:
        _log.warn("No {admin,readonly}_user/password found in config. file, "
                  "accessing DB without authentication")
    return db


def get_collection(config_file, admin=False, settings=None):
    if settings is None:
        settings = get_settings(config_file)
    db = get_database(admin=admin, settings=settings)
    return db[settings["collection"]]


def collection_keys(coll, sep='.'):
    """Get a list of all (including nested) keys in a collection.
    Examines the first document in the collection.

    :param sep: Separator for nested keys
    :return: List of str
    """
    def _keys(x, pre=''):
        for k in x:
            yield (pre + k)
            if isinstance(x[k], dict):
                for nested in _keys(x[k], pre + k + sep):
                    yield nested

    return list(_keys(coll.find_one()))
