__author__ = 'dang'

import logging
import random
import unittest

from matgendb.tests.common import MockQueryEngine
from matgendb.vv.diff import Differ, Delta

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
        'idlist': range(num),
        'zero': 0,
        'energy': random.random() * 5,
    }

#


class MyTestCase(unittest.TestCase):
    NUM_RECORDS = 10

    @classmethod
    def setUpClass(cls):
        mg = logging.getLogger("mg")
        mg.setLevel(logging.ERROR)
        mg.addHandler(logging.StreamHandler())

    def setUp(self):
        self.collections, self.engines = ['diff1', 'diff2'], []
        self.colors = [[None, None] for i in xrange(self.NUM_RECORDS)]
        self.energies = [[None, None] for i in xrange(self.NUM_RECORDS)]
        for c in self.collections:
            # Create mock query engine.
            self.engines.append(MockQueryEngine(collection=c, **db_config))
        for ei, engine in enumerate(self.engines):
            engine.collection.remove({})
            for i in xrange(self.NUM_RECORDS):
                rec = create_record(i)
                engine.collection.insert(rec)
                # save some vars for easy double-checking
                self.colors[i][ei] = rec['color']
                self.energies[i][ei] = rec['energy']

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

    def test_eqprops_same(self):
        """Keys and props, all are the same.
        """
        # Perform diff.
        df = Differ(key='name', props=['same'])
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), 0)

    def test_eqprops_different(self):
        """Keys and props, some props out of range.
        """
        # Perform diff.
        df = Differ(key='name', props=['color'])
        d = df.diff(*self.engines)
        # Calculate expected results.
        changed = sum((int(c[0] != c[1]) for c in self.colors))
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

    def test_numprops_same(self):
        """Keys and props, all are the same.
        """
        # Perform diff.
        df = Differ(key='name', deltas={"zero": "+-0.001"})
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), 0)

    def test_numprops_different(self):
        """Keys and props, some props different.
        """
        # Perform diff.
        delta = 0.5
        df = Differ(key='name', deltas={"energy": "+-{:f}".format(delta)})
        d = df.diff(*self.engines)
        # Calculate expected results.
        is_different = lambda a, b: abs(a - b) > delta
        changed = sum((int(is_different(c[0], c[1])) for c in self.energies))
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

    def test_numprops_different_pct(self):
        """Keys and props, some props different, check pct change.
        """
        # Perform diff.
        minus, plus = 10, 20
        df = Differ(key='name', deltas={"energy": "+{}-{}=%".format(plus, minus)})
        d = df.diff(*self.engines)

        # Calculate expected results.
        def is_different(a, b):
            pct = 100.0 * (b - a) / a
            return pct <= -minus or pct >= plus
        changed = sum((int(is_different(c[0], c[1])) for c in self.energies))

        # Check results.
        if len(d[Differ.CHANGED]) != changed:
            result = d[Differ.CHANGED]
            msg = "Values:\n"
            for i, e in enumerate(self.energies):
                if not is_different(*e):
                    continue
                msg += "{:d}) {:f} {:f}\n".format(i, e[0], e[1])
            msg += "Result:\n"
            for i, r in enumerate(result):
                msg += "{:d}) {} {}\n".format(i, r["old"], r["new"])
            self.assertEqual(len(d[Differ.CHANGED]), changed, msg=msg)

    # repeat this test a few more times
    test_numprops_different_pct1 = test_numprops_different_pct
    test_numprops_different_pct2 = test_numprops_different_pct
    test_numprops_different_pct3 = test_numprops_different_pct

    def test_delta(self):
        """Delta class parsing.
        """
        self.failUnlessRaises(ValueError, Delta, "foo")

    def test_delta_sign(self):
        """Delta class sign.
        """
        d = Delta("+-")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(-1, 0), False)
        self.assertEquals(d.cmp(-1, 1), True)

    def test_delta_val(self):
        """Delta class value, same absolute.
        """
        d = Delta("+-3")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(1, 4), False)
        self.assertEquals(d.cmp(1, 5), True)

    def test_delta_val(self):
        """Delta class value, different absolute.
        """
        d = Delta("+2.5-1.5")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(1, 3), False)
        self.assertEquals(d.cmp(3, 1), True)

    def test_delta_val(self):
        """Delta class value, same absolute equality.
        """
        d = Delta("+-3.0=")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(1, 4), True)
        self.assertEquals(d.cmp(4, 1), True)

    def test_delta_val(self):
        """Delta class value, same percentage.
        """
        d = Delta("+-25%")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(8, 4), True)
        self.assertEquals(d.cmp(8, 6), False)

    def test_delta_val(self):
        """Delta class value, same percentage equality.
        """
        d = Delta("+-25=%")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(8, 4), True)
        self.assertEquals(d.cmp(8, 6), True)

    def test_delta_val(self):
        """Delta class value, different percentage equality.
        """
        d = Delta("+50-25=%")
        self.assertEquals(d.cmp(0, 1), False)
        self.assertEquals(d.cmp(8, 4), True)
        self.assertEquals(d.cmp(8, 6), True)
        self.assertEquals(d.cmp(6, 8), False)
        self.assertEquals(d.cmp(6, 9), True)

if __name__ == '__main__':
    unittest.main()
