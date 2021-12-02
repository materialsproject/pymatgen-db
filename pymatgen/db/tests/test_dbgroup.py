"""
Unit tests for `dbgroup` module.
"""
__author__ = "Dan Gunter"
__copyright__ = "Copyright 2014, The Materials Project"
__email__ = "dkgunter@lbl.gov"
__date__ = "2014-04-29"

import json
import mongomock
import os
import tempfile
import unittest
from pymatgen.db.dbgroup import ConfigGroup
from pymatgen.db import dbconfig

_opj = os.path.join

mockdb = mongomock.MongoClient()
doc = {"hello": "world"}
mockdb.testdb.data.insert_one(doc)
# add some nested collections
mockcoll = ["data.a1", "data.a1.b1", "data.a1.b2", "data.a2"]
[mockdb.testdb[c].insert_one(doc) for c in mockcoll]


class MockQueryEngine:
    def __init__(self, **kwargs):
        self.kw = kwargs

    def __eq__(self, other):
        return other.kw == self.kw

    @property
    def collection(self):
        return mockdb.testdb[self.kw["collection"]]

    @property
    def db(self):
        class DB:
            _c = mockcoll

            def collection_names(self, x=None):
                return self._c

        return DB()


class Cfg:
    def __init__(self, v):
        self.settings = {"collection": v}
        self.collection = v

    def copy(self):
        return Cfg(self.collection)


class ConfigGroupTestCase(unittest.TestCase):
    def setUp(self):
        self.g = ConfigGroup(qe_class=MockQueryEngine)
        self.configs = [Cfg(f"qe{i:d}") for i in range(5)]

    def test_add(self):
        """ConfigGroup add and lookup"""
        keys = ["foo", "bar", "foo.a", "foo.b"]
        expect = {}
        for i, k in enumerate(keys):
            self.g.add(k, self.configs[i])
            expect[k] = MockQueryEngine(**self.configs[i].settings)
        self.assertEqual(self.g["foo"], expect["foo"])
        self.assertEqual(self.g["bar"], expect["bar"])
        self.assertEqual(self.g["bar*"], {"bar": expect["bar"]})
        self.assertEqual(self.g["foo.a"], expect["foo.a"])
        self.assertEqual(self.g["foo.*"], {"foo.a": expect["foo.a"], "foo.b": expect["foo.b"]})

    def test_add_path(self):
        """Add set of query engines from a path."""
        # directory of pretend configs
        d = tempfile.mkdtemp()
        try:
            # fill with some configs
            c = {}
            for root in ("foo", "bar"):
                for sub in ("a", "b.1", "b.2"):
                    config = {dbconfig.DB_KEY: root, dbconfig.COLL_KEY: sub}
                    filename = f"mg_core_{root}_{sub}.json"
                    with open(_opj(d, filename), "w") as fp:
                        json.dump(config, fp)
                    c[f"{root}.{sub}"] = config
            # read them
            self.g.add_path(d)
            # check all were added
            self.assertEqual(sorted(self.g.keys()), sorted(c.keys()))
            # check one
            qe1 = self.g["foo.a"].kw
            c1 = c["foo.a"]
            self.assertTrue(dict_subset(c1, qe1))
            # check with prefix
            self.g.set_prefix("foo.b")
            self.assertTrue(dict_subset(c["foo.b.1"], self.g["1"].kw))
            self.assertRaises(KeyError, self.g.__getitem__, "bla")
            # check list with prefix
            gkeys = sorted(self.g["*"].keys())
            self.assertEqual(gkeys, ["foo.b.1", "foo.b.2"])
            # check list w/o prefix
            self.g.set_prefix()
            gkeys = sorted(self.g["bar.b.*"].keys())
            self.assertEqual(gkeys, ["bar.b.1", "bar.b.2"])
        finally:
            # rm -r $d
            for f in os.listdir(d):
                os.unlink(os.path.join(d, f))
            os.rmdir(d)

    def test_uncache(self):
        """Remove cached query engine(s) from ConfigGroup."""
        keys = ("foo.a", "foo", "bar")
        for i in range(len(keys)):
            self.g.add(keys[i], self.configs[i])
        # force instantiation/caching
        for i in range(len(keys)):
            self.g[keys[i]]
        left_behind = self.g[keys[2]]
        # remove all foo from cache
        self.g.uncache("foo*")
        # check that they are not cached
        for i in range(2):
            self.assertRaises(KeyError, self.g._cached.__getitem__, keys[i])
        # check that un-removed remain
        self.assertEqual(self.g[keys[2]], left_behind)

    def test_expand(self):
        """Add multiple collections at once with 'expand'."""
        self.g.add("foo", Cfg("data"), expand=True)
        # check that data.* got added as foo.*
        keys = set(self.g.keys())
        expect = set(["foo"] + [f.replace("data", "foo") for f in mockcoll])
        self.assertEqual(expect, keys)


def dict_subset(a, b):
    for k in a.keys():
        if k not in b or b[k] != a[k]:
            return False
    return True


if __name__ == "__main__":
    unittest.main()
