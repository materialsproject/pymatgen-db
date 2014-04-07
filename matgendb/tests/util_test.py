"""
Tests for matgendb.util
"""
__author__ = 'dang'

import unittest
from matgendb.util import normalize_auth, collection_keys


class NormAuthTestCase(unittest.TestCase):
    """Test cases for normalize_auth().
    """
    def setUp(self):
        self.U, self.P = "joe", "secret"

    def _check(self, s):
        """Check that user/password matches expected.
        """
        self.failUnless(s["user"] == self.U)
        self.failUnless(s["password"] == self.P)

    def _check_absent(self, s):
        """Check that user/password is not present.
        """
        self.failIf("user" in s or "password" in s)

    def test_admin(self):
        s = {"admin_user": self.U, "admin_password": self.P}
        normalize_auth(s)
        self._check(s)
        s = {"admin_user": self.U, "admin_password": self.P}
        normalize_auth(s, admin=False)
        self._check_absent(s)

    def test_ro(self):
        s = {"readonly_user": self.U, "readonly_password": self.P}
        normalize_auth(s)
        self._check(s)
        s = {"readonly_user": self.U, "readonly_password": self.P}
        normalize_auth(s, readonly=False)
        self._check_absent(s)

    def test_plain(self):
        s = {"user": self.U, "password": self.P}
        normalize_auth(s)
        self._check(s)

    def test_order(self):
        s = {"readonly_user": self.U + "_1", "readonly_password": self.P,
             "admin_user": self.U + "_2", "admin_password": self.P}
        normalize_auth(s, readonly_first=False)
        self.assertEqual(s["user"], self.U + "_2")
        s = {"readonly_user": self.U + "_1", "readonly_password": self.P,
             "admin_user": self.U + "_2", "admin_password": self.P}
        normalize_auth(s, readonly_first=True)
        self.assertEqual(s["user"], self.U + "_1")


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
