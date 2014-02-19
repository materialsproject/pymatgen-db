"""
Utility functions used across scripts
"""
__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "1.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Dec 1, 2012"

import bson
import datetime
import json
import logging
import os
from pymongo.mongo_client import MongoClient


_log = logging.getLogger("mg.util")

DEFAULT_PORT = 27017
DEFAULT_CONFIG_FILE = "db.json"

DEFAULT_SETTINGS = [
    ("host", "localhost"),
    ("port", DEFAULT_PORT),
    ("database", "vasp"),
    # ("admin_user", None),
    # ("admin_password", None),
    # ("readonly_user", None),
    # ("readonly_password", None),
    # ("collection", "tasks"),
    # ("aliases_config", None),
    # ("mapi_key", None)
]


def get_settings(config_file):
    # Get input file.
    infile = None
    if config_file:
        infile = config_file
    elif os.path.exists(DEFAULT_CONFIG_FILE):
        infile = DEFAULT_CONFIG_FILE

    # Read settings from input file.
    if infile:
        config_settings = json.load(open(infile))
        # Allow some aliases
        for alias, real in (("user", "readonly_user"), ("password", "readonly_password")):
            if alias in config_settings:
                config_settings[real] = config_settings[alias]
                del config_settings[alias]
    else:
        config_settings = {}

    # Merge input file settings and defaults.
    settings = dict(DEFAULT_SETTINGS)
    settings.update(config_settings)

    return settings


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


def normalize_auth(settings, admin=True, readonly=True):
    """Transform the readonly/admin user and password to simple user/password,
    as expected by QueryEngine.

    :param settings: Connection settings
    :type settings: dict
    :param admin: Check for admin password
    :param readonly: Check for readonly password
    :return: Whether user/password are now in settings
    :rtype: bool
    :raise: KeyError if neither readonly, admin, or plain user/password are found
    """
    U, P = "user", "password"
    # If user/password, un-prefixed, exists, do nothing.
    if U in settings and P in settings:
        return True

    # Set prefixes
    prefixes = []
    if admin:
        prefixes.append("admin_")
    if readonly:
        prefixes.append("readonly_")

    # Look for first user/password matching.
    found = False
    for pfx in prefixes:
        ukey, pkey = pfx + U, pfx + P
        if ukey in settings and pkey in settings:
            settings[U] = settings[ukey]
            settings[P] = settings[pkey]
            found = True
            break

    return found


def get_collection(config_file, admin=False):
    db = get_database(config_file, admin=admin)
    settings = get_settings(config_file)
    return db[settings["collection"]]


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bson.objectid.ObjectId):
            return str(o)
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)
