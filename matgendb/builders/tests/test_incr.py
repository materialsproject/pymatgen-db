"""
Test the builders.incr module
"""
from unittest import TestCase

__author__ = 'Dan Gunter'
__created__ = 'April 12, 2014'

import mongomock
import unittest
from matgendb.builders.incr import *


# Global collection object
coll = mongomock.Connection().db.collection


def clear():
    coll.remove()


def add_records(n):
    obj = None
    for i in xrange(n):
        obj = {"n": i,
               "s": "foo-{:d}".format(i)}
        coll.insert(obj)
    return obj


class TestCollectionTracker(TestCase):

    extractors = [IdExtractor]

    def setUp(self):
        clear()
        self.trackers = {ex: CollectionTracker(coll, ex) for ex in self.extractors}

    def test_mark(self):
        op = Operation.other
        for ex, trk in self.trackers.iteritems():
            trk.set_mark(op)
            mark = trk.get_mark(op)
            self.assertEqual(mark, {}, "Expected empty mark")
            rec = add_records(10)
            trk.set_mark(op)
            mark = trk.get_mark(op)
            if ex is IdExtractor:
                expected = {'_id': {'$gt': rec['_id']}}
            else:
                print("class of ex = {}".format(ex.__class__.__name__))
                expected = None   # XXX: no other extractors yet
            self.assertEqual(mark, expected,
                             "Mark '{}' does not match '{}'"
                             .format(mark, expected))


    def test_get_mark(self):
        self.fail()

    def test_find(self):
        self.fail()

if __name__ == '__main__':
    unittest.main()

