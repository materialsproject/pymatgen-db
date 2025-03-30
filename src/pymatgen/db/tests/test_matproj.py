from __future__ import annotations

import unittest

from src.pymatgen.db.matproj import MPDB
from src.pymatgen.db.tests import common

has_mongo = common.has_mongo()


class MPDBTest(unittest.TestCase):
    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_queryresult(self):
        mpdb = MPDB()
        mpdb.create({"chemsys": "Fe-O"})
        entries = mpdb.get_entries_in_chemsys(["Fe", "O"])
        assert len(entries) > 0
