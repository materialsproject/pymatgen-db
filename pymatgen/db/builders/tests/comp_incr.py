"""
Component-level tests for builder.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "4/24/14"

# Stdlib
import logging
import time
import unittest

# Package
from pymatgen.db.tests.common import ComponentTest, get_component_logger

_log = get_component_logger("comp_incr")


class BuilderComponentTest(ComponentTest):
    EX_MOD = "pymatgen.db.builders.examples"

    def test_copy_builder(self):
        self._test_copy_builder(1)

    def test_copy_builder_parallel(self):
        self._test_copy_builder(8)

    def _test_copy_builder(self, ncores):
        # Init builder
        bld_args = [
            self.EX_MOD + ".copy_builder.CopyBuilder",
            "source=" + self.src_conf.name,
            "target=" + self.dst_conf.name,
            "crit={}",
            "-i",
            "copy:number",
            "-n",
            str(ncores),
        ]
        if _log.isEnabledFor(logging.DEBUG):
            bld_args.append("-vv")
        # Insert a new record #x
        addrec = lambda x: self.src.insert_one({"number": x, "data": [1, 2, 3], "name": f"mp-{x:d}"})
        # Add first batch of records
        map(addrec, list(range(1000)))
        # Run builder
        self.mgbuild(bld_args)
        # Count records in copied-to collection
        n = self.dst.count()
        self.assertTrue(n == 1000, "Bad count after 1st copy: " "expected=1000 got={:d}".format(n))
        # do a few more copies
        total, m, ovhd, rectm = n, (1, 100, 500, 1000, 501, 101), 0, {}
        for i, newrec in enumerate(m):
            _log.info(f"Build, #records = {newrec:d}")
            # Add records
            map(addrec, list(range(total, total + newrec)))
            # Copy
            t0 = time.time()
            self.mgbuild(bld_args)
            t1 = time.time()
            if newrec == 1:
                ovhd = t1 - t0
            else:
                rectm[newrec] = t1 - t0 - ovhd
            # count records in copied-to collection
            n = self.dst.count()
            total += newrec
            self.assertEqual(
                n,
                total,
                "Bad count after copy #{:d}: " "expected={:d} got={:d}".format(i + 2, total, n),
            )
        _log.info(f"Overhead = {ovhd:.1f} seconds")
        for sz in m[1:]:
            _log.info(f"{sz:d} = {rectm[sz]:g}s, {rectm[sz] / sz * 1e6:.0f}us/rec")

    def test_maxval_builder(self):
        self._test_maxval_builder(1)

    def test_maxval_builder_parallel(self):
        self._test_maxval_builder(8)

    def _test_maxval_builder(self, ncores):
        # Do an incremental build with the MaximumValueBuilder
        groups = ["A", "B", "C", "D"]
        # Init builder
        bld_args = [
            self.EX_MOD + ".maxvalue_builder.MaxValueBuilder",
            "source=" + self.src_conf.name,
            "target=" + self.dst_conf.name,
            "-i",
            "copy:recid",
            "-n",
            str(ncores),
        ]
        if _log.isEnabledFor(logging.DEBUG):
            bld_args.append("-vv")
        # Way to cycle groups
        get_group = lambda x, n: groups[:n][x % n]
        # Insert a new record #x
        ngrp = len(groups) - 1
        addrec = lambda x: self.src.insert_one({"recid": x, "value": x, "group": get_group(x, ngrp)})

        # Add first batch of records
        nrec = 10
        map(addrec, list(range(nrec)))

        # Run builder
        self.mgbuild(bld_args)

        # Check number of records in target
        ntarget = self.dst.count()
        self.assertEqual(ntarget, ngrp)

        # Check max values for each group
        group_maxes = {get_group(x, ngrp): x for x in range(nrec - 1, nrec - ngrp - 1, -1)}
        for rec in self.dst.find({}):
            self.assertEqual(rec["value"], group_maxes[rec["group"]])

        # Add some more records, and a new group
        rmin, rmax = 20, 25
        ngrp = len(groups)
        addrec = lambda x: self.src.insert_one({"recid": x, "value": x, "group": get_group(x, ngrp)})
        map(addrec, list(range(rmin, rmax)))

        # Re-run builder
        self.mgbuild(bld_args)

        # Check number of records in target
        ntarget = self.dst.count()
        self.assertEqual(ntarget, ngrp)

        # Check max values for each group
        group_maxes = {get_group(x, ngrp): x for x in range(rmin, rmax)}
        for rec in self.dst.find({}):
            self.assertEqual(rec["value"], group_maxes[rec["group"]])


if __name__ == "__main__":
    unittest.main()
