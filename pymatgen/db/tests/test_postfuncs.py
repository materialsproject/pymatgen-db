import pymongo
from pymongo import MongoClient

import uuid
import unittest
import pprint
from pymatgen.db.query_engine import QueryEngine, QueryResults
from pymatgen.db.tests import common

has_mongo = common.has_mongo()


class SandboxTest(unittest.TestCase):

    SBX = "testing"
    N = 100

    def qtx(self, crit, props):
        if props == None:
            props = {}
        crit["sbxd.e_above_hull"] = crit["e_above_hull"]
        props["sbxd"] = {"$elemMatch": {"id": self.SBX}}
        del crit["e_above_hull"]

    def rtx(self, doc):
        doc["add_fake_field"] = "test value"
        for item in doc["sbxd"]:
            if item["id"] == self.SBX:
                doc["e_above_hull"] = item["e_above_hull"]
        return doc

    def setUp(self):
        # Try a real mongodb
        if has_mongo:
            self.conn = pymongo.MongoClient()
            self.db_name = "test"
            self.db = self.conn[self.db_name]
            self.coll_name = f"sandboxes_{uuid.uuid4()}"
            self.coll = self.db[self.coll_name]
            for i in range(self.N):
                core_v, sbx_v = 0.1 * (i + 1), -0.1 * (i + 1)
                doc = {
                    "task_id": f"mp-{1000 + i:d}",
                    "sbxd": [
                        {"id": "core", "e_above_hull": core_v},
                        {"id": self.SBX, "e_above_hull": sbx_v},
                    ],
                    "sbxn": ["core", self.SBX],
                }
                doc.update({"state": "successful"})
                if i < 2:
                    pprint.pprint(doc)
                self.coll.insert_one(doc)

    def tearDown(self):
        if has_mongo:
            self.db.drop_collection(self.coll_name)

    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_no_post_funcs(self):
        qe = QueryEngine(
            connection=self.conn,
            database=self.db_name,
            collection=self.coll_name,
            aliases={},
            query_post=[],
            result_post=[],
        )
        cursor = qe.query()
        self.assertTrue(isinstance(cursor, QueryResults))
        n = 0
        for rec in cursor:
            pprint.pprint(f"RESULT: {rec}")
            # No Post proccessing should be done
            self.assertTrue("e_above_hull" not in rec)
            self.assertTrue("add_fake_field" not in rec)

            self.assertTrue("sbxd" in rec)
            n += 1
        # should find all tasks
        self.assertEqual(n, self.N)

    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_mongo_find(self):

        #
        qe = QueryEngine(
            connection=self.conn,
            database=self.db_name,
            collection=self.coll_name,
            aliases={},
            query_post=[self.qtx],
            result_post=[self.rtx],
        )
        result = self._test_find(qe, criteria={"e_above_hull": {"$lte": 0.0}}, properties={})

    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_with_properties(self):

        #
        qe = QueryEngine(
            connection=self.conn,
            database=self.db_name,
            collection=self.coll_name,
            aliases={},
            query_post=[self.qtx],
            result_post=[self.rtx],
        )
        result = self._test_find(
            qe,
            criteria={"e_above_hull": {"$lte": 0.0}},
            properties=["e_above_hull", "sbxd", "add_fake_field"],
        )

    def _test_find(self, qe, properties, criteria):
        cursor = qe.query(properties=properties, criteria=criteria)
        self.assertTrue(isinstance(cursor, QueryResults))
        n = 0
        for rec in cursor:
            pprint.pprint(f"RESULT: {rec}")
            self.assertTrue(rec["e_above_hull"] < 0)
            self.assertEqual(rec["add_fake_field"], "test value")
            n += 1
        # should find all tasks
        self.assertEqual(n, self.N)

    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_queryresult(self):

        qe = QueryEngine(
            connection=self.conn,
            database=self.db_name,
            collection=self.coll_name,
            aliases={},
            query_post=[self.qtx],
            result_post=[self.rtx],
        )
        result = qe.query(criteria={"e_above_hull": {"$lte": 0.0}}).sort("sbxd.e_above_hull", pymongo.ASCENDING)
        self.assertTrue(isinstance(result, QueryResults))
        self.assertEqual(len(result), self.N)
        self.assertTrue(result[0]["e_above_hull"] < 0)


if __name__ == "__main__":
    unittest.main()
