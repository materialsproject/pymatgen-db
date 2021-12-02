"""
Test the builders.incr module.

These tests use `mongomock` instead of a real MongoDB server.
"""
from unittest import TestCase

__author__ = "Dan Gunter"
__created__ = "April 12, 2014"

import mongomock
import unittest
from pymatgen.db.builders.incr import *


COLLECTION = "my_collection"
DATABASE = "db"

# Global collection object
conn = mongomock.MongoClient()
db = conn[DATABASE]
coll = db.my_collection
# Hacks for mongomock deficiencies
coll.database = db
db.collection_names = lambda x: [COLLECTION]


def clear():
    coll.remove()


def add_records(n, offs=0):
    obj = None
    for i in range(n):
        obj = {"n": i + offs, "s": f"foo-{i:d}"}
        coll.insert_one(obj)
    return obj


def dumpcoll(c):
    print(f"-- Collection '{c.name}' --")
    for rec in c.find():
        print(f">> {rec}")


class TestCollectionTrackerLL(TestCase):
    """Test low-level API."""

    def setUp(self):
        clear()
        self.trackers = {coll: CollectionTracker(coll)}

    def test_mark(self):
        for op in Operation.other, Operation.copy, Operation.build:
            # check with empty collection
            mark = Mark(coll, op, field="_id")
            self.assertEqual(mark.pos, {"_id": None})
            # add some records and see if it matches the last one
            rec = add_records(10)
            mark.update()
            self.assertEqual(mark.pos, {"_id": rec["_id"]})
            clear()

    def test_collection_tracker(self):
        index = "_id"
        for op in Operation.other, Operation.copy, Operation.build:
            rec = add_records(10)
            tracker = CollectionTracker(coll)
            tracker.save(Mark(coll, op, field=index).update())
            mark = tracker.retrieve(op, field=index)
            # dumpcoll(tracker.tracking_collection)
            # print("@@ mark pos={}".format(mark.pos))
            self.assertEqual(mark.pos, {index: rec[index]})
            clear()

    def test_collection_tracker_exist(self):
        # init, but do not create tracking collection
        tracker = CollectionTracker(coll, create=False)
        # check that collection is None and operations fail
        self.assertEqual(tracker.tracking_collection, None)
        self.assertRaises(NoTrackingCollection, tracker.save, ("foo",))
        self.assertRaises(NoTrackingCollection, tracker.save, (Operation.copy, "foo"))
        # create tracking collection, now it should exist
        tracker.create()
        self.assertNotEqual(tracker.tracking_collection, None)

    def test_query(self):
        index = "_id"
        op = Operation.copy
        tracker = CollectionTracker(coll)
        # get mark (start of coll.)
        mark = Mark(collection=coll, operation=op, field=index)
        # add records
        add_records(10)
        # get all records after mark (0..9)
        values = [r["n"] for r in coll.find(mark.query)]
        values.sort()
        # check that all 10 records are returned
        self.assertEqual(values, list(range(10)))
        # update and save mark
        tracker.save(mark.update())
        # retrieve saved mark
        mark = tracker.retrieve(operation=op, field=index)
        # get all records after mark (=0)
        values = [r["n"] for r in coll.find(mark.query)]
        # check that 0 records are returned
        self.assertEqual(values, [])
        # now add 10 more records, #'ed 10-19
        add_records(10, offs=10)
        # get all records after mark (10..19)
        values = [r["n"] for r in coll.find(mark.query)]
        values.sort()
        # check that next 10 records are returned
        self.assertEqual(values, list(range(10, 20)))


class TestCollectionTrackerHL(TestCase):
    """Test high-level API."""

    def setUp(self):
        clear()

    def test_tracked_qe(self):
        index, props = "_id", ["n"]
        qe = TrackedQueryEngine(
            track_operation=Operation.copy,
            track_field=index,
            connection=conn,
            collection=COLLECTION,
            database=DATABASE,
        )
        # Add new records
        add_records(10)
        # Check that we get all new records
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 10)
        # Set mark, now these records are 'old'
        qe.set_mark()
        # Check that we get no records
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 0)
        # Add more records
        add_records(5, offs=100)
        # Check that new records ONLY are retrieved
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 5)
        for rec in cur:
            self.assertGreaterEqual(rec["n"], 100)

    def test_findall(self):
        index, props = "_id", ["n"]
        qe = TrackedQueryEngine(
            track_operation=Operation.copy,
            track_field=index,
            connection=conn,
            collection=COLLECTION,
            database=DATABASE,
        )
        # Add new records
        add_records(10)
        # Check that we get all new records
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 10)
        # Set mark, now these records are 'old'
        qe.set_mark()
        # Check that we get no records
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 0)
        # ** Turn off tracking **
        qe.tracking = False
        # Check that we get *all* records
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 10)
        # Turn tracking back on
        qe.tracking = True
        # Check that we get no records, once again
        cur = qe.query(properties=props)
        self.assertEqual(len(cur), 0)


if __name__ == "__main__":
    unittest.main()
