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
conn = mongomock.Connection()
db = conn.db
coll = db.collection
# mongomock does this wrong
coll.database = db


def clear():
    coll.remove()


def add_records(n):
    obj = None
    for i in xrange(n):
        obj = {"n": i,
               "s": "foo-{:d}".format(i)}
        coll.insert(obj)
    return obj

def dumpcoll(c):
    print("-- Collection '{}' --".format(c.name))
    for rec in c.find():
        print(">> {}".format(rec))

class TestCollectionTracker(TestCase):

    def setUp(self):
        clear()
        self.trackers = {coll: CollectionTracker(coll)}

    def test_mark(self):
        for op in Operation.other, Operation.copy, Operation.build:
            # check with empty collection
            mark = Mark(coll, op, field='_id')
            self.assertEqual(mark.pos, {'_id': 0})
            # add some records and see if it matches the last one
            rec = add_records(10)
            mark.update()
            self.assertEqual(mark.pos, {'_id': rec['_id']})
            clear()

    def test_collection_tracker(self):
        index = '_id'
        for op in Operation.other, Operation.copy, Operation.build:
            rec = add_records(10)
            tracker = CollectionTracker(coll)
            tracker.save(Mark(coll, op, field=index))
            mark = tracker.retrieve(op, field=index)
            #dumpcoll(tracker.tracking_collection)
            self.assertEqual(mark.pos, {index: rec[index]})
            clear()

if __name__ == '__main__':
    unittest.main()

