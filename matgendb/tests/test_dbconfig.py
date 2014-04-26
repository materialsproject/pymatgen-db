"""
Unit tests for `dbconfig` module.
"""
__author__ = 'Dan Gunter'
__date__ = '2014-04-25'

import unittest
from matgendb.dbconfig import *

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


if __name__ == '__main__':
    unittest.main()
