from __future__ import annotations

import os
import unittest
import uuid

import bson
import pymongo

from pymatgen.db.query_engine import QueryEngine, QueryResults
from tests import common

has_mongo = common.has_mongo()

test_dir = os.path.join(os.path.dirname(__file__), "test_files")


class QueryResultsTest(unittest.TestCase):
    def setUp(self):
        if has_mongo:
            self.conn = pymongo.MongoClient()
            self.db_name = "test"
            self.db = self.conn[self.db_name]
            self.coll_name = f"tasks_{uuid.uuid4()}"
            self.coll = self.db[self.coll_name]
            with open(os.path.join(test_dir, "db_test", "GaLa.task.json")) as f:
                doc = bson.json_util.loads(f.read())
                self.coll.insert_one(doc)

    def tearDown(self):
        if has_mongo:
            self.db.drop_collection(self.coll_name)

    @unittest.skipUnless(has_mongo, "requires MongoDB server")
    def test_queryresult(self):
        qe = QueryEngine(
            connection=self.conn,
            database=self.db_name,
            collection=self.coll_name,
        )
        result = qe.query(
            criteria={"task_id": "mp-1002133"},
            properties=[
                "calcs_reversed.output.ionic_steps.e_0_energy",
                "calcs_reversed.output.ionic_steps.electronic_steps.e_0_energy",
            ],
        )
        assert isinstance(result, QueryResults)
        print(list(qe.query(criteria={"task_id": "mp-1002133"})))
        assert len(result) == 1
        doc = next(iter(result))
        assert "calcs_reversed.output.ionic_steps.e_0_energy" in doc
        v = doc["calcs_reversed.output.ionic_steps.e_0_energy"]
        assert isinstance(v, list)
        for elt in v:
            assert isinstance(elt, list)
            for n in elt:
                assert isinstance(n, float)
        assert "calcs_reversed.output.ionic_steps.electronic_steps.e_0_energy" in doc
        v = doc["calcs_reversed.output.ionic_steps.electronic_steps.e_0_energy"]
        for elt in v:
            assert isinstance(elt, list)
            for _elt in elt:
                assert isinstance(_elt, list)
                for n in _elt:
                    assert isinstance(n, float)
