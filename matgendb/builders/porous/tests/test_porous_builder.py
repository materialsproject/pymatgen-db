"""
Tests for db.builders.porous_builder
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '10/29/13'

## Imports
# Stdlib
import bz2
import json
import logging
import os
import unittest
# Package
from pymatpro.db.builders import porous_builder
from pymatpro.db.builders.tests.common import QueryEngine
from pymatpro.db.builders.tests.common import warn_no_db, skip_no_db
from pymatpro.db.util import get_test_dir

## Logging

_log = logging.getLogger("mg")
_hndlr = logging.StreamHandler()
_hndlr.setFormatter(logging.Formatter("%(levelname)s: %(msg)s"))
_log.addHandler(_hndlr)
if os.environ.get('MP_DEBUG', False):
    _log.setLevel(logging.DEBUG)
else:
    _log.setLevel(logging.WARNING)

## Classes & Functions


class PBTestCase(unittest.TestCase):

    has_db = True

    @classmethod
    def setUpClass(cls):
        """One-time setup.

        Put source data, from a local file, in MongoDB.
        """
        try:
            qe = QueryEngine("porous_materials")
        except:
            warn_no_db(_log)
            cls.has_db = False
            return
        coll = qe.collection  # internal MongoDB Collection obj
        coll.remove()  # clear old, to avoid duplication
        cls.add_from_file(coll)

    @classmethod
    def add_from_file(cls, coll):
        """Add each (newline-separated) record from an
        input file in the test directory, to the target collection.
        """
        path = os.path.join(get_test_dir(), 'ccmdb.json.bz2')
        f = bz2.BZ2File(path)
        for item in f:
            j = json.loads(item)
            coll.insert(j)

    def setUp(self):
        """Per-test setup.

        Create new Builder class and set into instance variable 'pb'.
        """
        if self.has_db:
            self.source = QueryEngine("porous_materials")
            self.target = QueryEngine("materials")
        else:
            self.source, self.target = None, None
        self.pb = porous_builder.PorousMaterialsBuilder(
            source=self.source, target=self.target, combine_status=True)

    def test_run(self):
        """Run the builder.
        """
        if not self.has_db:
            skip_no_db(_log, "Run the builder")
            return
        status = self.pb.run()
        self.assertEqual(status, 0, "run() returned non-zero status: {}".format(status))

    def test_schema(self):
        """Test the schema.
        """
        self.pb.validate_examples(self.fail)

if __name__ == '__main__':
    unittest.main()
