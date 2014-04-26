"""
Tests for matgendb.util
"""
__author__ = 'dang'

import unittest
from matgendb.util import collection_keys

class FakeCollection(object):
    """Collection that emulates find_one().
    """
    def __init__(self, data):
        self.data = data

    def find_one(self):
        return self.data


class KeysTestCase(unittest.TestCase):
    """Test collection_keys.
    """
    def test_flat(self):
        keys = ["a", "b", "C"]
        coll = FakeCollection(dict.fromkeys(keys))
        result = collection_keys(coll)
        self.assertEqual(set(keys), set(result))

    def test_nested(self):
        input = {"a": {"b": {"c": 1}}}
        coll = FakeCollection(input)
        result = collection_keys(coll)
        print("@@Result: {}".format(result))
        keys = ["a", "a.b", "a.b.c"]
        self.assertEqual(set(keys), set(result))

if __name__ == '__main__':
    unittest.main()
