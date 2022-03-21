"""
Common functions for tests
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "10/29/13"

# Stdlib
import logging
import os

import pymongo

# Third-party
from mongomock import MongoClient

# Package
from pymatgen.db.query_engine import QueryEngine

_log = logging.getLogger("pymatgen.db.tests")

TEST_FILES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "..",
    "test_files",
)


def has_mongo():
    """Determine if MongoDB is up and usable"""
    if os.environ.get("MP_FAKEMONGO"):
        mongo = False
    else:
        try:
            pymongo.MongoClient()
            mongo = True
        except:
            mongo = False
    return mongo


class MockQueryEngine(QueryEngine):
    """Mock (fake) QueryEngine, unless a real connection works.
    You can disable the attempt to do a real connection
    by setting MP_FAKEMONGO to anything
    """

    def __init__(
        self,
        host="127.0.0.1",
        port=27017,
        database="vasp",
        user=None,
        password=None,
        collection="tasks",
        aliases_config=None,
        default_properties=None,
    ):
        if has_mongo():
            try:
                QueryEngine.__init__(
                    self,
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    collection=collection,
                    aliases_config=aliases_config,
                    default_properties=default_properties,
                )
                _log.warning(f"Connected to real MongoDB at {host}:{port}")
                return  # actully connected! not mocked..
            except:
                _log.debug(f"Connection to real MongoDB at {host}:{port} failed. This is normal; using mock.")
        self.connection = MongoClient(host, port)
        self.db = self.connection[database]
        self._user, self._password = user, password
        self.host = host
        self.port = port
        self.database_name = database
        # colllection name is now a @property. the setter will set "self.collection" internally
        self.collection_name = collection
        self.set_aliases_and_defaults(aliases_config=aliases_config, default_properties=default_properties)
