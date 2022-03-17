"""
Pymatgen-db is a database add-on for the Python Materials Genomics (pymatgen)
materials analysis library. It enables the creation of Materials
Project-style MongoDB databases for management of materials data and
provides a clean and intuitive web ui for exploring that data. A query engine
is also provided to enable the easy translation of MongoDB docs to useful
pymatgen objects for analysis purposes.
"""

import os

__author__ = "Shyue Ping Ong, Dan Gunter"
__date__ = "Jul 22 2017"
__version__ = "2022.3.17"


from .query_engine import QueryEngine

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".pmgrc.yaml")


def _load_mgdb_settings():
    try:
        import ruamel.yaml as yaml

        with open(SETTINGS_FILE) as f:
            d = yaml.load(f)
    except OSError:
        return {}
    return d


SETTINGS = _load_mgdb_settings()