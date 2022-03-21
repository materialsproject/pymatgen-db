"""
Utility functions used across scripts.
"""

import datetime
import json
import logging

import bson
from pymongo.mongo_client import MongoClient

from pymatgen.db.config import DBConfig

DEFAULT_PORT = DBConfig.DEFAULT_PORT
DEFAULT_CONFIG_FILE = DBConfig.DEFAULT_FILE
DEFAULT_SETTINGS = DBConfig.DEFAULT_SETTINGS

_log = logging.getLogger("mg.util")


class MongoJSONEncoder(json.JSONEncoder):
    """
    JSON encoder to support ObjectIDs and datetime used in Mongo.
    """

    def default(self, o):
        """
        Override default to support ObjectID and datetime.
        """
        if isinstance(o, bson.objectid.ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


def get_settings(config_file):
    """
    Get settings from file.
    """
    cfg = DBConfig(config_file)
    return cfg.settings


def get_database(config_file=None, settings=None, admin=False, **kwargs):
    """
    Get a database object from a config file.
    """
    d = get_settings(config_file) if settings is None else settings
    conn = MongoClient(host=d["host"], port=d["port"], **kwargs)
    db = conn[d["database"]]
    try:
        user = d["admin_user"] if admin else d["readonly_user"]
        passwd = d["admin_password"] if admin else d["readonly_password"]
        db.authenticate(user, passwd)
    except (KeyError, TypeError, ValueError):
        _log.warning("No {admin,readonly}_user/password found in config. file, accessing DB without authentication")
    return db


def get_collection(config_file, admin=False, settings=None):
    """
    Get a collection from a config file.
    :param config_file Path to filename
    :param admin Whether to use admin credentials. Default to False.
    :param settings Whether to override settings or obtain from config file (None).
    """
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
            yield pre + k
            if isinstance(x[k], dict):
                yield from _keys(x[k], pre + k + sep)

    return list(_keys(coll.find_one()))
