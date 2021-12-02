"""
Tests for builders.schema utility module.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "11/1/13"

import unittest
from pymatgen.db.builders import schema

# most basic schema
basic = {
    "a": "__int__",
    "b": "__float__",
    "arr": ["__float__"],
    "oarr": [{"x": "__int__"}],
}

# basic schema with some optional parts
optionals = {
    "a": "__int__",
    "?b": "__float__",
    "arr": ["__float__"],
    "?oarr": [{"x": "__int__"}],
}


class MyTestCase(unittest.TestCase):
    def test_basic_validate(self):
        inputs = [
            ({"a": 1, "b": 2.3, "arr": [1.0], "oarr": []}, True),
            ({"a": 1, "b": 2.3, "arr": [1.0], "oarr": [{"x": 1}]}, True),
            ({"a": 1, "b": 2.3, "arr": [1.0], "oarr": [{"z": 1}]}, False),
            ({"a": 1, "b": 2.3, "arr": [1.0], "oarr": [{"x": [1, 2]}]}, False),
            ({"a": 1, "b": 2.3, "arr": [1.0], "oarr": [{"x": Exception}]}, False),
        ]
        sch = schema.Schema(basic)
        for doc, expect_ok in inputs:
            self.check(sch, doc, expect_ok)

    def test_opt_validate(self):
        inputs = [
            ({"a": 1, "arr": [1.0]}, True),
            ({"a": 1, "arr": [1.0], "b": 1.2}, True),
            ({"a": 2, "arr": [], "oarr": [{"z": 1}]}, False),
            ({"a": 2, "arr": [], "oarr": [{"x": 1}]}, True),
            ({"a": 1}, False),
        ]
        sch = schema.Schema(optionals)
        for doc, expect_ok in inputs:
            self.check(sch, doc, expect_ok)

    def test_unknown_type(self):
        try:
            schema.Schema({"a": "__foo__"})
        except schema.SchemaTypeError:
            pass

    def check(self, sch, doc, expect_ok):
        result = sch.validate(doc)
        if result is None:
            self.assertTrue(expect_ok, self.false_positive(doc))
        else:
            self.assertFalse(expect_ok, self.false_negative(doc, result))

    def false_positive(self, input_):
        return f"input ({input_}) should have failed to validate"

    def false_negative(self, input_, result):
        return f"input ({input_}) should have been valid, got {result}"


class JsonSchemaTests(unittest.TestCase):
    def setUp(self):
        self.example_js = {
            # "title": "Example Schema",
            "type": "object",
            "properties": {
                "firstName": {"type": "string"},
                "lastName": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["lastName", "firstName"],
        }
        # alt. is reverse of 'required'
        self.example_js2 = self.example_js.copy()
        self.example_js2["required"] = list(reversed(self.example_js["required"]))
        #
        self.example_mine = {
            "firstName": "__string__",
            "lastName": "__string__",
            "?age": "__int__",
        }
        self.example_mine_nounder = {
            "firstName": "string",
            "lastName": "string",
            "?age": "int",
        }

    def test_create_js(self):
        for ex in (self.example_mine, self.example_mine_nounder):
            s = schema.Schema(ex)
            self.assertIn(s.json_schema(), (self.example_js, self.example_js2))


if __name__ == "__main__":
    unittest.main()
