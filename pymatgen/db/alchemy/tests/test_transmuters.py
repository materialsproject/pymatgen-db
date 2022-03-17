#!/usr/bin/env python

"""
Created on Mar 5, 2012
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Mar 5, 2012"

import os
import unittest

from pymatgen.apps.borg.queen import BorgQueen
from pymatgen.transformations.standard_transformations import (
    OxidationStateDecorationTransformation,
    PartialRemoveSpecieTransformation,
    SubstitutionTransformation,
)
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from pymatgen.db.alchemy.transmuters import QeTransmuter
from pymatgen.db.creator import VaspToDbTaskDrone
from pymatgen.db.query_engine import QueryEngine

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "test_files")


class QeTransmuterTest(unittest.TestCase):

    qe = None
    conn = None

    @classmethod
    def setUpClass(cls):
        try:
            drone = VaspToDbTaskDrone(database="qetransmuter_unittest")
            queen = BorgQueen(drone)
            queen.serial_assimilate(os.path.join(test_dir, "db_test", "success_mp_aflow"))
            cls.conn = MongoClient()
            cls.qe = QueryEngine(database="qetransmuter_unittest")
        except ConnectionFailure:
            cls.qe = None
            cls.conn = None

    def test_transmute(self):
        if QeTransmuterTest.qe is None:
            self.skipTest("No MongoDB present")
        crit = {}
        trans = [
            SubstitutionTransformation({"Zn": "Mg"}),
            OxidationStateDecorationTransformation({"B": 3, "O": -2, "Mg": 2, "Tb": 3}),
            PartialRemoveSpecieTransformation("Mg2+", 0.5, algo=PartialRemoveSpecieTransformation.ALGO_COMPLETE),
        ]
        self.qep = QeTransmuter(QeTransmuterTest.qe, crit, trans, extend_collection=10)
        trans_structures = self.qep.transformed_structures
        self.assertEqual(len(trans_structures), 3)
        for s in trans_structures:
            self.assertEqual(s.final_structure.composition.reduced_formula, "Tb2Mg(BO2)10")

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.drop_database("qetransmuter_unittest")


if __name__ == "__main__":
    unittest.main()
