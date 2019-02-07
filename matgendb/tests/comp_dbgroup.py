"""
Component-level tests for dbgroup module.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '5/2/14'

# Stdlib
import json
import logging
import pymongo
import os; _opj = os.path.join
import sys
import tempfile
import time
import unittest
# Package
from matgendb.tests.common import ComponentTest
from matgendb.dbconfig import DB_KEY, COLL_KEY
from matgendb.dbgroup import ConfigGroup

_log = logging.getLogger("comp_dbgroup")
_h = logging.StreamHandler(sys.stdout)
_log.addHandler(_h)
_log.setLevel(logging.INFO)

class DBGroupComponentTest(ComponentTest):
    DB_COLL = {
        "marvel": ["spiderman", "spiderman.amazing", "spiderman.spectacular", "hulk"],
        "dc": ["flash", "flash.garrick", "flash.barry", "flash.wally", "superman"]
    }
    DB_COLL_CFG = {
        "marvel": ["spiderman", "hulk"],
        "dc": ["flash", "superman"]
    }

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._config_names = []
        self._conn = pymongo.MongoClient()
        self.create_configs()
        self.create_dbs()

    def tearDown(self):
        for fname in os.listdir(self._tmpdir):
            os.unlink(_opj(self._tmpdir, fname))
        os.rmdir(self._tmpdir)

    def create_configs(self):
        p = self._tmpdir
        cfg = {"host": "localhost", "port": 27017}
        for db, collections in self.DB_COLL_CFG.items():
            cfg[DB_KEY] = db
            for coll in collections:
                cfg[COLL_KEY] = coll
                with open(_opj(p, "{}_{}.json".format(db, coll)), "w") as f:
                    json.dump(cfg, f)
                self._config_names.append("{}.{}".format(db, coll))

    def create_dbs(self):
        for dbname, collections in self.DB_COLL.items():
            db = self._conn[dbname]
            for collname in collections:
                coll = db[collname]
                coll.insert({"hello": collname})

    def test_readall(self):
        """Read all configurations in a directory.
        """
        g = ConfigGroup()
        t0 = time.time()
        g.add_path(self._tmpdir)
        t1 = time.time()
        _log.debug("Time to scan directory = {:.3g}s".format(t1 - t0))
        expect = set(self._config_names)
        got = set(g.keys())
        self.assertEqual(expect, got)

    def test_expand(self):
        """Expand configurations to get full list of collections.
        """
        g = ConfigGroup().add_path(self._tmpdir)
        _log.debug("Base: {}".format(g.keys()))
        t0 = time.time()
        g.expand("marvel.*")
        t1 = time.time()
        _log.debug("Expanded in {:.3g}s: {}".format(t1 - t0, g.keys()))
        # expect expanded marvel, but just configured dc
        marvel = map(lambda val: 'marvel.' + val, self.DB_COLL['marvel'])
        dc = map(lambda val: 'dc.' + val, self.DB_COLL_CFG['dc'])
        expect = set(marvel + dc)
        got = set(g.keys())
        self.assertEqual(expect, got)

    def test_sandbox(self):
        """Combine expand and prefix to make a sandbox.
        """
        g = ConfigGroup().add_path(self._tmpdir)
        for i, sandbox in enumerate(["marvel.spiderman", "dc.flash"]):
            g.expand("{}*".format(sandbox))
            _log.debug("Expanded {} keys: {}".format(sandbox,g.keys()))
            g.set_prefix(sandbox)
            qe, expect_name = None, None
            if i == 0:
                for wow in "amazing", "spectacular":
                    qe = g[wow]
                    expect_name = "spiderman.{}".format(wow)
                    self.assertEqual(qe.collection.name, expect_name)
                    self.assertEqual(qe.db.name, "marvel")
            elif i == 1:
                for who in "garrick", "barry", "wally":
                    qe = g[who]
                    expect_name = "flash.{}".format(who)
                    self.assertEqual(qe.collection.name, expect_name)
                    self.assertEqual(qe.db.name, "dc")
            # only entry in db should be hello:<collname>
            _log.debug("Query QE={} collection={}".format(qe, qe.collection.name))
            cur = qe.query()
            row = cur[0]
            self.assertEqual(row["hello"], expect_name)


if __name__ == '__main__':
    unittest.main()