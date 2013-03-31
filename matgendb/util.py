"""
Utility functions used across scripts
"""
__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "1.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Dec 1, 2012"

import json
import os

DEFAULT_PORT = 27017

DEFAULT_SETTINGS = [
    ("host", "localhost"),
    ("port", DEFAULT_PORT),
    ("database", "vasp"),
    ("admin_user", None),
    ("admin_password", None),
    ("readonly_user", None),
    ("readonly_password", None),
    ("collection", "tasks"),
    ("aliases_config", None)
]


def get_settings(config_file):
    if config_file:
        with open(config_file) as f:
            return json.load(f)
    elif os.path.exists("db.json"):
        with open("db.json") as f:
            return json.load(f)
    else:
        return dict(DEFAULT_SETTINGS)
