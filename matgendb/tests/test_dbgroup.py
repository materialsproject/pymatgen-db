"""
Unit tests for `dbgroup` module.
"""
__author__ = "Dan Gunter"
__copyright__ = "Copyright 2014, The Materials Project"
__email__ = "dkgunter@lbl.gov"
__date__ = "2014-04-29"

import json
import os
import tempfile
import unittest
from matgendb.dbgroup import QEGroup
from matgendb import dbconfig

_opj = os.path.join

class MockQueryEngine(object):
    def __init__(self, **kwargs):
        self.kw = kwargs

class QEGroupTestCase(unittest.TestCase):
    def setUp(self):
        self.g = QEGroup(qe_class=MockQueryEngine)

    def test_add(self):
        """QEGroup add and lookup
        """
        self.g.add("foo", "qe1")\
            .add("bar", "qe2")\
            .add("foo.a", "qe3")\
            .add("foo.b", "qe4")
        self.assertEqual(self.g["foo"], "qe1")
        self.assertEqual(self.g["bar"], "qe2")
        self.assertEqual(self.g["bar*"], {"bar": "qe2"})
        self.assertEqual(self.g["foo.a"], "qe3")
        self.assertEqual(self.g["foo.*"],
                         {"foo.a": "qe3", "foo.b": "qe4"})

    def test_add_path(self):
        """Add set of query engines from a path.
        """
        # directory of pretend configs
        d = tempfile.mkdtemp()
        try:
            # fill with some configs
            c = {}
            for root in ("foo", "bar"):
                for sub in ("a", "b.1", "b.2"):
                    config = {
                        dbconfig.DB_KEY: root,
                        dbconfig.COLL_KEY: sub
                    }
                    filename = "mg_core_{}_{}.json".format(root, sub)
                    with open(_opj(d, filename), "w") as fp:
                        json.dump(config, fp)
                    c["{}.{}".format(root, sub)] = config
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

def dict_subset(a, b):
    for k in a.iterkeys():
        if k not in b or b[k] != a[k]:
            return False
    return True

if __name__ == '__main__':
    unittest.main()
