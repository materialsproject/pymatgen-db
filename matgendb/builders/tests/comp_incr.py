"""
Component-level tests for builder.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/24/14'

# Stdlib
import logging
import sys
import time
import unittest
# Package
from matgendb.tests.common import ComponentTest

_log = logging.getLogger("comp_build")
_h = logging.StreamHandler(sys.stdout)
_log.addHandler(_h)
_log.setLevel(logging.INFO)

class BuilderComponentTest(ComponentTest):
    BUILD_CMD = ["mgbuild", "build"]

    def call_build(self, options):
        args = self.BUILD_CMD[:]
        return self.run_command(args, options)

    def test_builder(self):
        self.add_records(self.src, 1000)
        options = (
            ('incr', None),
            ('module', 'matgendb.builders.examples'),
            ('builder', 'file_builders'),
            ('kvp', 'input_file=' + self.src_conf.name),
            ('kvp', 'target=' + self.dst_conf.name),
        )
        self.call_build(options)
        # count records in copied-to collection
        n = self.dst.count()
        self.assert_(n == 1000,
                     "Bad count after 1st copy: "
                     "expected=1000 got={:d}".format(n))
        # do a few more copies
        total, m, ovhd, rectm = n, (1, 100, 500, 1000, 501, 101), 0, {}
        for i, newrec in enumerate(m):
            _log.info("Build, #records = {:d}". format(newrec))
            # Add records and copy
            self.add_records(self.src, newrec)
            t0 = time.time()
            self.call_build(options)
            t1 = time.time()
            if newrec == 1:
                ovhd = t1 - t0
            else:
                rectm[newrec] = t1 - t0 - ovhd
            # count records in copied-to collection
            n = self.dst.count()
            total += newrec
            self.assertEqual(n, total,
                         "Bad count after copy #{:d}: "
                         "expected={:d} got={:d}".format(i + 2, total, n))
        _log.info("Overhead = {:.1f} seconds".format(ovhd))
        for sz in m[1:]:
            _log.info("{:d} = {:g}s, {:.0f}us/rec".format(sz, rectm[sz], rectm[sz] / sz * 1e6))

if __name__ == '__main__':
    unittest.main()