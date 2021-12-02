"""
Unit tests for vv.validate module
"""
__author__ = "Dan Gunter"
__copyright__ = "Copyright 2012-2013, The Materials Project"
__version__ = "1.0"
__maintainer__ = "Dan Gunter"
__email__ = "dkgunter@lbl.gov"
__status__ = "Development"
__date__ = "1/31/13"

import time
import unittest
import pymatgen.db.vv.validate as vv
import pymatgen.db.vv.util as vu


class TestCollectionFilter(unittest.TestCase):
    def test_Timing(self):
        e = vu.ElapsedTime()
        with vu.Timing(elapsed=e):
            time.sleep(0.2)
        self.assertAlmostEqual(e.value, 0.2, places=1)
        # test some other modes of invocation
        with vu.Timing() as t:
            x = 1
        loglvl = 10

        class FakeLog:
            def __init__(self, testclass):
                self.tc = testclass

            def log(self, lvl, msg):
                self.tc.assertEqual(lvl, loglvl)

        with vu.Timing(log=FakeLog(self), level=loglvl):
            x = 1

    def test_ConstraintOperator_base(self):
        "Test the ConstraintOperator class."
        for bad_op in (None, "foobar", "<>", "#"):
            self.assertRaises(ValueError, vv.ConstraintOperator, bad_op)

    def test_ConstraintOperator_ineq(self):
        "Test the ConstraintOperator class, inequalities."
        for ineq in "<", ">", ">=", "<=":
            obj = vv.ConstraintOperator(">")
            self.assertTrue(obj.is_inequality())

    def test_ConstraintOperator_size(self):
        "Test the ConstraintOperator class sizes."
        obj = vv.ConstraintOperator("size>")
        self.assertTrue(obj.is_size() and obj.is_size_gt())
        obj = vv.ConstraintOperator("size")
        self.assertTrue(obj.is_size() and obj.is_size_eq())
        obj = vv.ConstraintOperator("size$")
        self.assertTrue(obj.is_size() and obj.is_variable())

    def test_ConstraintOperator_rev(self):
        "Test the ConstraintOperator class, reverse."
        obj = vv.ConstraintOperator("=")
        obj.reverse()
        self.assertTrue(obj.is_neq())

    def test_ConstraintOperator_type(self):
        "Test the ConstraintOperator class for types"
        obj = vv.ConstraintOperator("type")
        self.assertTrue(obj.is_type())

    def test_Field(self):
        "Test the Field class"
        for bad_field in (None, 10):
            self.assertRaises(ValueError, vv.Field, bad_field)

    def test_Field_subfields(self):
        "Test the Field class for subfields"
        f = vv.Field("foo.bar/baz")
        self.assertEqual(f.has_subfield(), True)
        self.assertEqual(f.name, "foo.bar")
        self.assertEqual(f.full_name, "foo.bar.baz")
        self.assertEqual(f.sub_name, "baz")

    def test_Field_aliases(self):
        "Test the Field class for aliases"
        a = {"foo": "bar"}
        f = vv.Field("foo", aliases=a)
        self.assertEqual(f.name, "bar")
        f = vv.Field("baz", aliases=a)
        self.assertEqual(f.name, "baz")

    def test_Constraint(self):
        "Test the Constraint class"
        for f, o, v in ((None, None, None), (1, 2, 3), ("a", "b", "c")):
            self.assertRaises(ValueError, vv.Constraint, f, o, v)
        obj = vv.Constraint(vv.Field("foo"), vv.ConstraintOperator(">"), 10)
        self.assertFalse(obj.passes(None)[0])
        self.assertFalse(obj.passes("dude")[0])
        self.assertFalse(obj.passes(10)[0])
        self.assertTrue(obj.passes(11)[0])

    def test_Constraint_init(self):
        "Test the Constraint class init variations"
        obj = vv.Constraint("foo", ">", 10)

    def test_Constraint_type(self):
        "Test the Constraint class for types"
        obj = vv.Constraint("foo", "type", "number")
        self.assertFalse(obj.passes("123")[0])
        self.assertFalse(obj.passes(True)[0])
        self.assertTrue(obj.passes(123)[0])
        self.assertTrue(obj.passes(1.23)[0])
        obj = vv.Constraint("foo", "type", "string")
        self.assertTrue(obj.passes("123")[0])
        self.assertFalse(obj.passes(True)[0])
        self.assertFalse(obj.passes(123)[0])
        self.assertFalse(obj.passes(1.23)[0])
        obj = vv.Constraint("foo", "type", "bool")
        self.assertFalse(obj.passes("123")[0])
        self.assertTrue(obj.passes(True)[0])
        self.assertFalse(obj.passes(123)[0])
        self.assertFalse(obj.passes(1.23)[0])

    def test_Projection(self):
        """Test Projection class"""
        # Empty
        p = vv.Projection()
        self.assertEqual(p.to_mongo(), {})
        # 1 field
        p.add(vv.Field("one"))
        expect = {"one": 1}
        self.assertEqual(p.to_mongo(), expect)
        # 1 field with static size
        szop = vv.ConstraintOperator(vv.ConstraintOperator.SIZE)
        p.add(vv.Field("one"), szop, 10)
        expect.update({"one": {"$slice": 11}})
        self.assertEqual(p.to_mongo(), expect)
        # a field with variable size
        szop = vv.ConstraintOperator(vv.ConstraintOperator.SIZE + "$")
        p.add(vv.Field("two"), szop, "foo")
        expect.update({"two": 1, "foo": 1})
        self.assertEqual(p.to_mongo(), expect)
        # subfields
        p = vv.Projection()
        p.add(vv.Field("a/bee"))
        self.assertEqual(p.to_mongo(), {"a.bee": 1})

    def test_ConstraintGroup(self):
        "Test ConstraintGroup class"
        CG = vv.ConstraintGroup
        foobar = vv.Field("foo.bar/baz")
        obj = CG(foobar)
        self.assertEqual(obj.has_array(), False)
        self.assertEqual(obj.get_conflicts(), [])
        # add constraint
        op, val = vv.ConstraintOperator(">"), 10
        obj.add_constraint(op, val)
        self.assertEqual(obj.has_array(), True)

    def test_ConstraintGroup_exists(self):
        "Test ConstraintGroup class, exists addition"
        CG = vv.ConstraintGroup
        foobar = vv.Field("foo.bar")
        obj = CG(foobar)
        op, val = vv.ConstraintOperator(">"), 10
        obj.add_constraint(op, val)
        obj.add_existence(rev=False)
        # expect 1 constraint and auxiliary existence constraint
        self.assertTrue(len(obj.constraints) == 1)
        self.assertEqual(obj.constraints[0].op, op)
        self.assertEqual(obj.constraints[0].value, val)
        self.assertEqual(len(obj.existence_constraints), 1)
        self.assertTrue(obj.existence_constraints[0].op.is_exists())
        self.assertEqual(obj.existence_constraints[0].value, True)

    def test_MongoClause(self):
        "Test MongoClause class"
        self.assertRaises(AssertionError, vv.MongoClause, None)
        fld = vv.Field("foo")
        op = vv.ConstraintOperator(">=")
        cn = vv.Constraint(fld, op, 10)
        obj = vv.MongoClause(cn)
        self.assertTrue(obj.query_loc == vv.MongoClause.LOC_MAIN)

    def test_MongoClause_where(self):
        "Test MongoClause class for where"
        fld = vv.Field("foo")
        for suffix, where in zip(("$", ">", ""), (True, True, True)):
            sz = "size" + suffix
            op = vv.ConstraintOperator(sz)
            cn = vv.Constraint(fld, op, 10)
            obj = vv.MongoClause(cn)
            if where:
                self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
            else:
                self.assertFalseEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)

    def test_MongoClause_expr(self):
        "Test MongoClause class generated expression"
        fld = "foo"
        val = 10
        for op, r_op in ((">=", "$lt"), ("<", "$gte"), ("=", "$ne")):
            cn = vv.Constraint(fld, op, val)
            obj = vv.MongoClause(cn)
            expected = {fld: {r_op: val}}
            self.assertEqual(obj.expr, expected)
        obj = vv.MongoClause(vv.Constraint(fld, "!=", val))
        self.assertEqual(obj.expr, {fld: val})

    def test_MongoClause_size(self):
        "Test MongoClause class for sizes"
        fld = "foo"
        val = 10
        # reversed
        for op, r_op in (("size>", "<="), ("size<", ">=")):
            obj = vv.MongoClause(vv.Constraint(fld, op, val))
            expected = f"this.{fld}.length {r_op} {val}"
            self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
            self.assertEqual(obj.expr, expected)
        # not reversed
        for op, r_op in (("size>", ">"), ("size<", "<")):
            obj = vv.MongoClause(vv.Constraint(fld, op, val), rev=False)
            expected = f"this.{fld}.length {r_op} {val}"
            self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
            self.assertEqual(obj.expr, expected)
        # variable
        obj = vv.MongoClause(vv.Constraint("foo", "size$", "bar"))
        self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
        self.assertEqual(obj.expr, "this.foo.length != this.bar")
        # variable not reversed
        obj = vv.MongoClause(vv.Constraint("foo", "size$", "bar"), rev=False)
        self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
        self.assertEqual(obj.expr, "this.foo.length == this.bar")
        # eq, reversed, in where
        obj = vv.MongoClause(vv.Constraint("foo", "size", 10))
        self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
        self.assertEqual(obj.expr, "this.foo.length != 10")
        # not reversed should be in main (but never used?)
        obj = vv.MongoClause(vv.Constraint("foo", "size", 10), rev=False)
        self.assertEqual(obj.query_loc, vv.MongoClause.LOC_MAIN)
        self.assertEqual(obj.expr, {"foo": {"$size": 10}})

    def test_MongoClause_type(self):
        "Test MongoClause class for types"
        fld, op = "foo", "type"
        for rev, whereop in ((True, "!="), (False, "==")):
            for val, type_js in (
                ("int", "number"),
                ("str", "string"),
                ("bool", "boolean"),
                ("number", "number"),
            ):
                obj = vv.MongoClause(vv.Constraint(fld, op, val), rev=rev)
                self.assertEqual(obj.query_loc, vv.MongoClause.LOC_WHERE)
                expected = f'typeof this.{fld} {whereop} "{type_js}"'
                self.assertEqual(obj.expr, expected)

    def test_MongoQuery_base(self):
        "Test MongoQuery class"
        q = vv.MongoQuery()
        self.assertRaises(AttributeError, q.add_clause, None)
        c = vv.MongoClause(vv.Constraint("foo", ">", 10))
        q.add_clause(c)
        m = q.to_mongo()
        self.assertEqual(m, c.expr)

    def test_MongoQuery_exists(self):
        "Test MongoQuery class, with an exists clause"
        q = vv.MongoQuery()
        c = vv.MongoClause(vv.Constraint("foo", "exists", True))
        q.add_clause(c)
        m = q.to_mongo()
        self.assertEqual(m, c.expr)

    def test_MongoQuery_where(self):
        "Test MongoQuery class, with where clauses"
        q = vv.MongoQuery()
        c1 = vv.MongoClause(vv.Constraint("foo", "size", 10))
        c2 = vv.MongoClause(vv.Constraint("bar", "size", 10))
        q.add_clause(c1)
        q.add_clause(c2)
        # no disjunction
        m = q.to_mongo(False)
        w = "this.{}.length != 10 || this.{}.length != 10"
        wheres = (w.format("foo", "bar"), w.format("bar", "foo"))
        self.assertTrue(m["$where"] in wheres)
        # disjunction
        m = q.to_mongo()
        w = "this.{}.length != 10 || this.{}.length != 10"
        wheres = (w.format("foo", "bar"), w.format("bar", "foo"))
        mwhere = m["$or"][0]["$where"]
        self.assertTrue(mwhere in wheres)
        # where and non-where together
        q.add_clause(vv.MongoClause(vv.Constraint("foo", "<=", 10)))
        m = q.to_mongo(False)
        w = "this.{}.length != 10 || this.{}.length != 10"
        self.assertTrue(m["$where"] in wheres and m["foo"] == {"$gt": 10})

    def test_violations(self):
        "Test error determination in CollectionValidator.why_bad"
        obj = vv.Validator()
        # main & where clause, both fail
        q = vv.MongoQuery()
        q.add_clause(vv.MongoClause(vv.Constraint("foo", "size>", 2)))
        q.add_clause(vv.MongoClause(vv.Constraint("bar", ">", 1)))
        rec = {"foo": [0], "bar": 0}
        reasons = obj._get_violations(q, rec)
        self.assertEqual(len(reasons), 2)
        for r in reasons:
            if r.field == "bar":
                self.assertTrue(r.op == ">" and r.got_value == 0 and r.expected_value == 1)
        # all pass
        q = vv.MongoQuery()
        q.add_clause(vv.MongoClause(vv.Constraint("foo", "size>", 2)))
        q.add_clause(vv.MongoClause(vv.Constraint("bar", ">", 1)))
        rec = {"foo": [0, 1, 2], "bar": 9}
        reasons = obj._get_violations(q, rec)
        rtuples = [r.as_tuple() for r in reasons]
        print("\n".join(map(str, rtuples)))
        self.assertEqual(len(reasons), 0)

    def test_get_mongo(self):
        "Test get_mongo() function"
        import math

        with self.assertRaises(ValueError):
            for rec in [1, 2, 3], "foo":
                vv.mongo_get(rec, "a")
        for rec in {}, None, "":
            self.assertEqual(vv.mongo_get(rec, "a", "dee-fault"), "dee-fault")
        rec = {
            "a": {
                "apple": {
                    "red": "delicious",
                    "green": "grannysmith",
                    "blue": "venutian",
                },
                "anumber": 2,
            },
            "e": math.e,
        }
        default = "mittens"
        # these should be found
        for key, expected in (
            ("a.apple.green", "grannysmith"),
            ("a.anumber", 2),
            ("e", math.e),
        ):
            self.assertEqual(vv.mongo_get(rec, key, default), expected)
            # these should not
        for key in "a.apple.orange", "x", "", "z.zebra.", ".":
            self.assertEqual(vv.mongo_get(rec, key, default), default)


if __name__ == "__main__":
    unittest.main()
