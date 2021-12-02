"""
Utility functions used across scripts.
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

from pymatgen.db.dbconfig import DBConfig

# Backwards compatibility from refactor to `dbconfig` module
# Copy of functions that were moved
from pymatgen.db.dbconfig import normalize_auth

# Copy of global constants that were moved
DEFAULT_PORT = DBConfig.DEFAULT_PORT
DEFAULT_CONFIG_FILE = DBConfig.DEFAULT_FILE
DEFAULT_SETTINGS = DBConfig.DEFAULT_SETTINGS

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


def get_database(config_file=None, settings=None, admin=False, **kwargs):
    d = get_settings(config_file) if settings is None else settings
    conn = MongoClient(host=d["host"], port=d["port"], **kwargs)
    db = conn[d["database"]]
    try:
        user = d["admin_user"] if admin else d["readonly_user"]
        passwd = d["admin_password"] if admin else d["readonly_password"]
        db.authenticate(user, passwd)
    except (KeyError, TypeError, ValueError):
        _log.warn("No {admin,readonly}_user/password found in config. file, " "accessing DB without authentication")
    return db


def get_collection(config_file, admin=False, settings=None):
    if settings is None:
        settings = get_settings(config_file)
    db = get_database(admin=admin, settings=settings)
    return db[settings["collection"]]


def collection_keys(coll, sep="."):
    """Get a list of all (including nested) keys in a collection.
    Examines the first document in the collection.

    :param sep: Separator for nested keys
    :return: List of str
    """

    def _keys(x, pre=""):
        for k in x:
            yield (pre + k)
            if isinstance(x[k], dict):
                yield from _keys(x[k], pre + k + sep)

    return list(_keys(coll.find_one()))


def csv_list(l):
    """Format list to a string with comma-separated values."""
    if len(l) == 0:
        return ""
    return ", ".join(map(str, l))


def quotable(v):
    if isinstance(v, int) or isinstance(v, float):
        return str(v)
    return f"'{v}'"


def csv_dict(d):
    """Format dict to a string with comma-separated values."""
    if len(d) == 0:
        return "{}"
    return "{" + ", ".join([f"'{k}': {quotable(v)}" for k, v in d.items()]) + "}"


def kvp_dict(d):
    """Format dict to key=value pairs."""
    return ", ".join([f"{k}={quotable(v)}" for k, v in d.items()])
