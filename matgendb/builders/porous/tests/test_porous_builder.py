"""
Tests for db.builders.porous_builder
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '10/29/13'

# Imports
import logging
import unittest

from matgendb.builders.tests.common import MockQueryEngine
from matgendb.builders.porous import porous_builder as pb


_log = logging.getLogger("mg.porous.test")


class PBTestCase(unittest.TestCase):
    def test_setup(self):
        """Setup builder with mocked MongoDB connection.
        """
        b = pb.PorousMaterialsBuilder()
        q1, q2 = map(lambda c: MockQueryEngine(port=-1, collection=c),
                     ["a", "b"])
        b.setup(q1, q2)

if __name__ == '__main__':
    unittest.main()
