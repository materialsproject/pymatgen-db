import unittest

from pymatgen.db.matproj import MPDB
from pymatgen.db.tests import common

has_mongo = common.has_mongo()


class MPDBTest(unittest.TestCase):
    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_queryresult(self):
        mpdb = MPDB()
        mpdb.create({"chemsys": "Fe-O"})
        entries = mpdb.get_entries_in_chemsys(["Fe", "O"])
        self.assertTrue(len(entries) > 0)
