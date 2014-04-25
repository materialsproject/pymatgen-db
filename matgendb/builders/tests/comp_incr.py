"""
Component-level tests for incremental builder.

Requires a local MongoDB server, and runs the
`mgbuild` command, so also requires that pymatgen-db is
loaded into the environment.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/24/14'

import json
import logging
import subprocess
import sys
import tempfile
import time

_log = logging.getLogger("reg_incr")
_h = logging.StreamHandler()
_log.addHandler(_h)
_log.setLevel(logging.INFO)

DB = 'testdb'
SRC = 'source'
DST = 'dest'

def connect(clear=False):
    """Connect to Mongo DB

    :return: pymongo Database
    """
    c = pymongo.MongoClient()
    db = c[DB]
    if clear:
        for coll in SRC, DST:
            db[coll].remove()
    return db

def record(i):
    return {
        "number": i,
        "data": [
            1, 2, 3
        ],
        "name": "mp-{:d}".format(i)
    }

def add_records(coll, n):
    for i in xrange(n):
        coll.insert(record(i))

def create_configs():
    base = {"host": "localhost",
            "port": 27017,
            "database": DB,
            "collection": None}
    files = []
    for coll in (SRC, DST):
        f = tempfile.NamedTemporaryFile(suffix=".json")
        base['collection'] = coll
        json.dump(base, f)
        f.flush()
        files.append(f)
    return files

# Check if we can run tests
run_tests = True
try:
    import pymongo
    connect()
except:
    _log.error("Could not connect to MongoDB server")
    run_tests = False

######################################

def main():
    """Run regression tests.
    """
    Test1()
    return 0

class RegressionFailure(Exception):
    pass

class Regression(object):
    BUILD_CMD = ["mgbuild", "build"]

    def __init__(self):
        self.db = connect(True)
        self.src, self.dst = self.db[SRC], self.db[DST]
        self.src_conf, self.dst_conf = create_configs()
        try:
            self.run()
        finally:
            self.cleanup()

    def run(self):
        pass

    def cleanup(self):
        pass

    def call_build(self, options):
        args = self.BUILD_CMD[:]
        for key, value in options:
            args.append("--{}".format(key))
            if value:
                args.append(value)
        _log.info("run: {}".format(' '.join(args)))
        return subprocess.call(args)

    def assert_(self, fact, msg):
        if not fact:
            raise RegressionFailure(msg)

class Test1(Regression):
    def run(self):
        add_records(self.src, 1000)
        options = (
            ('incr', None),
            ('module', 'matgendb.builders.examples'),
            ('builder', 'copy_builder'),
            #('kvp', 'crit=\"\"'),
            ('kvp', 'source=' + self.src_conf.name),
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
            # Add records and copy
            add_records(self.src, newrec)
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
            self.assert_(n == total,
                         "Bad count after copy #{:d}: "
                         "expected={:d} got={:d}".format(i + 2, total, n))
        _log.info("Overhead = {:.1f} seconds".format(ovhd))
        for sz in m[1:]:
            _log.info("{:d} = {:g}s, {:.0f}us/rec".format(sz, rectm[sz], rectm[sz] / sz * 1e6))

if __name__ == '__main__':
    res = 0
    if run_tests:
        res = main()
    else:
        res = 1
        _log.warn("Aborting tests")
    sys.exit(res)