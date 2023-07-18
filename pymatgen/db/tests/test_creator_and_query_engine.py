#!/usr/bin/env python

"""
Created on Jun 19, 2012
"""
from __future__ import annotations

import os
import unittest
import warnings

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from pymatgen.apps.borg.queen import BorgQueen
from pymatgen.core.structure import Structure
from pymatgen.db.creator import VaspToDbTaskDrone
from pymatgen.db.query_engine import QueryEngine
from pymatgen.db.tests import common
from pymatgen.electronic_structure.dos import CompleteDos
from pymatgen.entries.computed_entries import ComputedEntry

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 19, 2012"

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files")

has_mongo = common.has_mongo()


class VaspToDbTaskDroneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if has_mongo:
            try:
                cls.conn = MongoClient()
            except ConnectionFailure:
                cls.conn = None
        else:
            cls.conn = None

    @unittest.skipUnless(has_mongo, "MongoDB connection required")
    def test_get_valid_paths(self):
        drone = VaspToDbTaskDrone(simulate_mode=True)
        all_paths = []
        for path in os.walk(os.path.join(test_dir, "db_test")):
            all_paths.extend(drone.get_valid_paths(path))
        assert len(all_paths) == 6

    @unittest.skipUnless(has_mongo, "MongoDB connection required")
    def test_to_from_dict(self):
        drone = VaspToDbTaskDrone(database="wacky", simulate_mode=True)
        d = drone.as_dict()
        drone = VaspToDbTaskDrone.from_dict(d)
        assert drone.simulate
        assert drone.database == "wacky"

    @unittest.skipUnless(has_mongo, "MongoDB connection required")
    def test_assimilate(self):
        """Borg assimilation code.
        This takes too long for a unit test!
        """
        simulate = VaspToDbTaskDroneTest.conn is None
        drone = VaspToDbTaskDrone(
            database="creator_unittest",
            simulate_mode=simulate,
            parse_dos=True,
            compress_dos=1,
        )
        queen = BorgQueen(drone)
        queen.serial_assimilate(os.path.join(test_dir, "db_test"))
        data = queen.get_data()
        assert len(data) == 6
        if VaspToDbTaskDroneTest.conn:
            db = VaspToDbTaskDroneTest.conn["creator_unittest"]
            data = db.tasks.find()
            assert db.tasks.count_documents({}) == 6
            warnings.warn("Actual db insertion mode.")

        for d in data:
            dir_name = d["dir_name"]
            if dir_name.endswith("killed_mp_aflow"):
                assert d["state"] == "killed"
                assert not d["is_hubbard"]
                assert d["pretty_formula"] == "SiO2"
            elif dir_name.endswith("stopped_mp_aflow"):
                assert d["state"] == "stopped"
                assert d["pretty_formula"] == "ThFe5P3"
            elif dir_name.endswith("success_mp_aflow"):
                assert d["state"] == "successful"
                assert d["pretty_formula"] == "TbZn(BO2)5"
                self.assertAlmostEqual(d["output"]["final_energy"], -526.66747274, 4)
            elif dir_name.endswith("Li2O_aflow"):
                assert d["state"] == "successful"
                assert d["pretty_formula"] == "Li2O"
                self.assertAlmostEqual(d["output"]["final_energy"], -14.31446494, 6)
                assert len(d["calculations"]) == 2
                assert d["input"]["is_lasph"] is False
                assert d["input"]["xc_override"] is None
                assert d["oxide_type"] == "oxide"
            elif dir_name.endswith("Li2O"):
                assert d["state"] == "successful"
                assert d["pretty_formula"] == "Li2O"
                self.assertAlmostEqual(d["output"]["final_energy"], -14.31337758, 6)
                assert len(d["calculations"]) == 1
                assert len(d["custodian"]) == 1
                assert len(d["custodian"][0]["corrections"]) == 1
            elif dir_name.endswith("Li2O_aflow_lasph"):
                assert d["state"] == "successful"
                assert d["pretty_formula"] == "Li2O"
                self.assertAlmostEqual(d["output"]["final_energy"], -13.998171, 6)
                assert len(d["calculations"]) == 2
                assert d["input"]["is_lasph"] is True
                assert d["input"]["xc_override"] == "PS"

        if VaspToDbTaskDroneTest.conn:
            warnings.warn("Testing query engine mode.")
            qe = QueryEngine(database="creator_unittest")
            assert len(qe.query()) == 6
            # Test mappings by query engine.
            for r in qe.query(
                criteria={"pretty_formula": "Li2O"},
                properties=[
                    "dir_name",
                    "energy",
                    "calculations",
                    "input",
                    "oxide_type",
                ],
            ):
                if r["dir_name"].endswith("Li2O_aflow"):
                    self.assertAlmostEqual(r["energy"], -14.31446494, 4)
                    assert len(r["calculations"]) == 2
                    assert r["input"]["is_lasph"] is False
                    assert r["input"]["xc_override"] is None
                    assert r["oxide_type"] == "oxide"
                elif r["dir_name"].endswith("Li2O"):
                    self.assertAlmostEqual(r["energy"], -14.31337758, 4)
                    assert len(r["calculations"]) == 1
                    assert r["input"]["is_lasph"] is False
                    assert r["input"]["xc_override"] is None

            # Test lasph
            e = qe.get_entries({"dir_name": {"$regex": "lasph"}})
            assert len(e) == 1
            assert e[0].parameters["is_lasph"] is True
            assert e[0].parameters["xc_override"] == "PS"

            # Test query one.
            d = qe.query_one(criteria={"pretty_formula": "TbZn(BO2)5"}, properties=["energy"])
            self.assertAlmostEqual(d["energy"], -526.66747274, 4)

            d = qe.get_entries_in_system(["Li", "O"])
            assert len(d) == 3
            assert isinstance(d[0], ComputedEntry)
            assert d[0].data["oxide_type"] == "oxide"

            s = qe.get_structure_from_id(d[0].entry_id)
            assert isinstance(s, Structure)
            assert s.formula == "Li2 O1"

            assert isinstance(qe.get_dos_from_id(d[0].entry_id), CompleteDos)

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.drop_database("creator_unittest")


if __name__ == "__main__":
    unittest.main()
