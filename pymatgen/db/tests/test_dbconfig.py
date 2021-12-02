"""
Unit tests for `dbconfig` module.
"""
__author__ = "Dan Gunter"
__date__ = "2014-04-25"

import json
import tempfile
import unittest
from pymatgen.db.dbconfig import DBConfig, normalize_auth
from pymatgen.db.dbconfig import ConfigurationFileError


class NormAuthTestCase(unittest.TestCase):
    """Test cases for normalize_auth()."""

    def setUp(self):
        self.U, self.P = "joe", "secret"

    def _check(self, s):
        """Check that user/password matches expected."""
        self.assertTrue(s["user"] == self.U)
        self.assertTrue(s["password"] == self.P)

    def _check_absent(self, s):
        """Check that user/password is not present."""
        self.assertFalse("user" in s or "password" in s)

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
        s = {
            "readonly_user": self.U + "_1",
            "readonly_password": self.P,
            "admin_user": self.U + "_2",
            "admin_password": self.P,
        }
        normalize_auth(s, readonly_first=False)
        self.assertEqual(s["user"], self.U + "_2")
        s = {
            "readonly_user": self.U + "_1",
            "readonly_password": self.P,
            "admin_user": self.U + "_2",
            "admin_password": self.P,
        }
        normalize_auth(s, readonly_first=True)
        self.assertEqual(s["user"], self.U + "_1")


class SettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "host": "localhost",
            "port": 27017,
            "database": "foo",
            "user": "guy",
            "password": "knock-knock",
            "aliases": {},
        }

    def _aliased_cfg(self):
        """Imitate authorization de-aliasing."""
        cfg = self.cfg.copy()
        cfg["readonly_password"] = cfg["password"]
        cfg["readonly_user"] = cfg["user"]
        return cfg

    def test_init_file(self):
        """Create DBConfig from file or path."""
        # sending file obj, or its path, should have same effect
        tmp = "dbconfigtest.json"
        with open(tmp, "w") as f:
            json.dump(self.cfg, f)
            f.flush()
            # reset file to beginning
        with open(tmp) as f:
            d1 = DBConfig(config_file=f)
        d2 = DBConfig(config_file=tmp)
        self.assertEqual(d1.settings, d2.settings)
        self.assertEqual(d2.settings, self._aliased_cfg())

    def test_init_dict(self):
        """Create DBConfig from dict object."""
        d1 = DBConfig(config_dict=self.cfg)
        self.assertEqual(d1.settings, self._aliased_cfg())

    def test_init_junk_file(self):
        """Check error when creating DBConfig from bad input file."""
        tf = tempfile.NamedTemporaryFile("w", delete=False)
        tf.write("JUNK")
        tf.close()
        self.assertRaises(ConfigurationFileError, DBConfig, config_file=tf.name)


if __name__ == "__main__":
    unittest.main()
