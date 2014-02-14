__author__ = 'dang'

import unittest

import json
import random
import tempfile

from matgendb.tests.common import MockQueryEngine
from matgendb.vv.diff import Differ

#

db_config = {
    'host': 'localhost',
    'port': 27017,
    'database': 'test'
}


def recname(num):
    return 'item-{:d}'.format(num)


def create_record(num):
    return {
        'name': recname(num),
        'color': random.choice(("red", "orange", "green", "indigo", "taupe", "mauve")),
        'same': 'yawn',
        'idlist': range(num)
    }

#


class MyTestCase(unittest.TestCase):
    NUM_RECORDS = 10

    def setUp(self):
        self.collections, self.engines = ['diff1', 'diff2'], []
        self.colors = [[None, None] for i in xrange(self.NUM_RECORDS)]
        for c in self.collections:
            # Create mock query engine.
            self.engines.append(MockQueryEngine(collection=c, **db_config))
        for ei, engine in enumerate(self.engines):
            engine.collection.remove({})
            for i in xrange(self.NUM_RECORDS):
                rec = create_record(i)
                engine.collection.insert(rec)
                # save color for easy double-checking
                self.colors[i][ei] = rec['color']

    def test_key_same(self):
        """Keys only and all keys are the same.
        """
        # Perform diff.
        df = Differ(key='name')
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.NEW]), 0)
        self.assertEqual(len(d[Differ.MISSING]), 0)

    def test_key_different(self):
        """Keys only and keys are different.
        """
        # Add one different record to each collection.
        self.engines[0].collection.insert(create_record(self.NUM_RECORDS + 1))
        self.engines[1].collection.insert(create_record(self.NUM_RECORDS + 2))
        # Perform diff.
        df = Differ(key='name')
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.MISSING]), 1)
        self.assertEqual(d[Differ.MISSING][0]['name'], recname(self.NUM_RECORDS + 1))
        self.assertEqual(len(d[Differ.NEW]), 1)
        self.assertEqual(d[Differ.NEW][0]['name'], recname(self.NUM_RECORDS + 2))

    def test_props_same(self):
        """Keys and props, all are the same.
        """
        # Perform diff.
        df = Differ(key='name', props=['same'])
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), 0)

    def test_props_different(self):
        """Keys and props, some props different.
        """
        # Perform diff.
        df = Differ(key='name', props=['color'])
        d = df.diff(*self.engines)
        # Calculate expected results.
        changed = sum((int(c[0] != c[1]) for c in self.colors))
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

if __name__ == '__main__':
    unittest.main()
