"""
Test vv.diff module
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"

import logging
import random
import unittest

from pymatgen.db.tests.common import MockQueryEngine
from pymatgen.db.vv.diff import Differ, Delta

#

db_config = {
    "host": "localhost",
    "port": 27017,
    "database": "test",
    "aliases_config": {"aliases": {}, "defaults": {}},
}


def recname(num):
    return f"item-{num:d}"


def create_record(num):
    return {
        "name": recname(num),
        "color": random.choice(("red", "orange", "green", "indigo", "taupe", "mauve")),
        "same": "yawn",
        "idlist": list(range(num)),
        "zero": 0,
        "energy": random.random() * 5 - 2.5,
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
        self.collections, self.engines = ["diff1", "diff2"], []
        self.colors = [[None, None] for i in range(self.NUM_RECORDS)]
        self.energies = [[None, None] for i in range(self.NUM_RECORDS)]
        for c in self.collections:
            # Create mock query engine.
            self.engines.append(MockQueryEngine(collection=c, **db_config))
        for ei, engine in enumerate(self.engines):
            engine.collection.delete_many({})
            for i in range(self.NUM_RECORDS):
                rec = create_record(i)
                engine.collection.insert_one(rec)
                # save some vars for easy double-checking
                self.colors[i][ei] = rec["color"]
                self.energies[i][ei] = rec["energy"]

    def test_key_same(self):
        """Keys only and all keys are the same."""
        # Perform diff.
        df = Differ(key="name")
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.NEW]), 0)
        self.assertEqual(len(d[Differ.MISSING]), 0)

    def test_key_different(self):
        """Keys only and keys are different."""
        # Add one different record to each collection.
        self.engines[0].collection.insert_one(create_record(self.NUM_RECORDS + 1))
        self.engines[1].collection.insert_one(create_record(self.NUM_RECORDS + 2))
        # Perform diff.
        df = Differ(key="name")
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.MISSING]), 1)
        self.assertEqual(d[Differ.MISSING][0]["name"], recname(self.NUM_RECORDS + 1))
        self.assertEqual(len(d[Differ.NEW]), 1)
        self.assertEqual(d[Differ.NEW][0]["name"], recname(self.NUM_RECORDS + 2))

    def test_eqprops_same(self):
        """Keys and props, all are the same."""
        # Perform diff.
        df = Differ(key="name", props=["same"])
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), 0)

    def test_eqprops_different(self):
        """Keys and props, some props out of range."""
        # Perform diff.
        df = Differ(key="name", props=["color"])
        d = df.diff(*self.engines)
        # Calculate expected results.
        changed = sum(int(c[0] != c[1]) for c in self.colors)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

    def test_numprops_same(self):
        """Keys and props, all are the same."""
        # Perform diff.
        df = Differ(key="name", deltas={"zero": Delta("+-0.001")})
        d = df.diff(*self.engines)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), 0)

    def test_numprops_different(self):
        """Keys and props, some props different."""
        # Perform diff.
        delta = 0.5
        df = Differ(key="name", deltas={"energy": Delta(f"+-{delta:f}")})
        d = df.diff(*self.engines)
        # Calculate expected results.
        is_different = lambda a, b: abs(a - b) > delta
        changed = sum(int(is_different(e[0], e[1])) for e in self.energies)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

    def test_numprops_different_sign(self):
        """Keys and props, some props different."""
        # Perform diff.
        df = Differ(key="name", deltas={"energy": Delta("+-")})
        d = df.diff(*self.engines)
        # Calculate expected results.
        is_different = lambda a, b: a < 0 < b or b < 0 < a
        changed = sum(int(is_different(e[0], e[1])) for e in self.energies)
        # Check results.
        self.assertEqual(len(d[Differ.CHANGED]), changed)

    def test_numprops_different_pct(self):
        """Keys and props, some props different, check pct change."""
        # Perform diff.
        minus, plus = 10, 20
        df = Differ(key="name", deltas={"energy": Delta(f"+{plus}-{minus}=%")})
        d = df.diff(*self.engines)

        # Calculate expected results.
        def is_different(a, b):
            pct = 100.0 * (b - a) / a
            return pct <= -minus or pct >= plus

        changed = sum(int(is_different(e[0], e[1])) for e in self.energies)

        # Check results.
        if len(d[Differ.CHANGED]) != changed:
            result = d[Differ.CHANGED]
            msg = "Values:\n"
            for i, e in enumerate(self.energies):
                if not is_different(*e):
                    continue
                msg += f"{i:d}) {e[0]:f} {e[1]:f}\n"
            msg += "Result:\n"
            for i, r in enumerate(result):
                msg += "{:d}) {} {}\n".format(i, r["old"], r["new"])
            self.assertEqual(len(d[Differ.CHANGED]), changed, msg=msg)

    # repeat this test a few more times
    test_numprops_different_pct1 = test_numprops_different_pct
    test_numprops_different_pct2 = test_numprops_different_pct
    test_numprops_different_pct3 = test_numprops_different_pct

    def test_delta(self):
        """Delta class parsing."""
        self.assertRaises(ValueError, Delta, "foo")

    def test_delta_sign(self):
        """Delta class sign."""
        d = Delta("+-")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(-1, 0), False)
        self.assertEqual(d.cmp(-1, 1), True)

    def test_delta_val(self):
        """Delta class value, same absolute."""
        d = Delta("+-3")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(1, 4), False)
        self.assertEqual(d.cmp(1, 5), True)

    def test_delta_val2(self):
        """Delta class value, different absolute."""
        d = Delta("+2.5-1.5")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(1, 3), False)
        self.assertEqual(d.cmp(3, 1), True)

    def test_delta_val3(self):
        """Delta class value, same absolute equality."""
        d = Delta("+-3.0=")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(1, 4), True)
        self.assertEqual(d.cmp(4, 1), True)

    def test_delta_val4(self):
        """Delta class value, same percentage."""
        d = Delta("+-25%")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(8, 4), True)
        self.assertEqual(d.cmp(8, 6), False)

    def test_delta_val5(self):
        """Delta class value, same percentage equality."""
        d = Delta("+-25=%")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(8, 4), True)
        self.assertEqual(d.cmp(8, 6), True)

    def test_delta_val6(self):
        """Delta class value, different percentage equality."""
        d = Delta("+50-25=%")
        self.assertEqual(d.cmp(0, 1), False)
        self.assertEqual(d.cmp(8, 4), True)
        self.assertEqual(d.cmp(8, 6), True)
        self.assertEqual(d.cmp(6, 8), False)
        self.assertEqual(d.cmp(6, 9), True)

    def test_delta_plus(self):
        """Delta class value 'plus only'."""
        d = Delta("+50")
        self.assertEqual(d.cmp(0, 50), False)
        self.assertEqual(d.cmp(0, 51), True)
        self.assertEqual(d.cmp(10, 5), False)
        d = Delta("+50=")
        self.assertEqual(d.cmp(0, 50), True)
        d = Delta("+50%")
        self.assertEqual(d.cmp(10, 25), True)
        self.assertEqual(d.cmp(25, 10), False)

    def test_delta_minus(self):
        """Delta class value 'minus only'."""
        d = Delta("-50")
        self.assertEqual(d.cmp(0, 50), False)
        self.assertEqual(d.cmp(51, 0), True)
        self.assertEqual(d.cmp(5, 10), False)
        d = Delta("-50=")
        self.assertEqual(d.cmp(50, 0), True)
        d = Delta("-50%")
        self.assertEqual(d.cmp(25, 10), True)
        self.assertEqual(d.cmp(10, 25), False)


if __name__ == "__main__":
    unittest.main()
