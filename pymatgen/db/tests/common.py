"""
Common functions for tests
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "10/29/13"

# Stdlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import traceback
import unittest

# Third-party
from mongomock import MongoClient
import pymongo

# Package
from pymatgen.db.query_engine import QueryEngine
from pymatgen.db.builders.incr import CollectionTracker

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
                _log.debug(
                    "Connection to real MongoDB at {}:{} failed. " "This is normal; using mock.".format(host, port)
                )
        self.connection = MongoClient(host, port)
        self.db = self.connection[database]
        self._user, self._password = user, password
        self.host = host
        self.port = port
        self.database_name = database
        # colllection name is now a @property. the setter will set "self.collection" internally
        self.collection_name = collection
        self.set_aliases_and_defaults(aliases_config=aliases_config, default_properties=default_properties)


# -----------------------------------
# Component test classes / functions
# -----------------------------------


def get_component_logger(name, strm=sys.stdout):
    log = logging.getLogger(name)
    if "TEST_DEBUG" in os.environ:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    _h = logging.StreamHandler(strm)
    log.addHandler(_h)
    return log


class ComponentTest(unittest.TestCase):
    DB = "testdb"
    SRC = "source"
    DST = "dest"

    MGBUILD_CMD = ["mgbuild", "run"]

    def setUp(self):
        self.db = self.connect(True)
        self.src, self.dst = self.db[self.SRC], self.db[self.DST]
        self.src_conf, self.dst_conf = self.create_configs()

    def mgbuild(self, args):
        try:
            s = subprocess.check_output(self.MGBUILD_CMD + args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            print(f"ERROR: {err.output}")
            raise
        return s

    def connect(self, clear=False):
        """Connect to Mongo DB

        :return: pymongo Database
        """
        c = pymongo.MongoClient()
        db = c[self.DB]
        if clear:
            for coll in self.SRC, self.DST:
                db[coll].remove()
                tcoll = coll + "." + CollectionTracker.TRACKING_NAME
                db[tcoll].remove()  # remove tracking as well
        return db

    def get_record(self, i):
        return {"number": i, "data": [1, 2, 3], "name": f"mp-{i:d}"}

    def add_records(self, coll, n):
        for i in range(n):
            coll.insert_one(self.get_record(i))

    def create_configs(self):
        base = {
            "host": "localhost",
            "port": 27017,
            "database": self.DB,
            "collection": None,
        }
        files = []
        for coll in (self.SRC, self.DST):
            f = tempfile.NamedTemporaryFile(suffix=".json")
            base["collection"] = coll
            json.dump(base, f)
            f.flush()
            files.append(f)
        return files

    def tearDown(self):
        pass

    def run_command(self, args, options):
        """Run the command-line given by the list
        in `args`, adding the dictionary given by
        options as long-form --{key}=value pairs.
        """
        for key, value in options:
            args.append(f"--{key}")
            if value:
                args.append(value)
        return subprocess.call(args)
