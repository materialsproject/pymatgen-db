#!/usr/bin/env python

"""
Created on Jun 19, 2012
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 19, 2012"

import unittest
import os
import warnings

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pymatgen.apps.borg.queen import BorgQueen

from matgendb.creator import VaspToDbTaskDrone

test_dir = os.path.join(os.path.dirname(__file__), "..", "..",
                        'test_files')

try:
    conn = MongoClient()
    simulate = False
except ConnectionFailure:
    simulate = True


class VaspToDbTaskDroneTest(unittest.TestCase):

    def test_get_valid_paths(self):
        drone = VaspToDbTaskDrone()
        all_paths = []
        for path in os.walk(os.path.join(test_dir, 'db_test')):
            all_paths.extend(drone.get_valid_paths(path))
        self.assertEqual(len(all_paths), 5)

    def test_assimilate(self):
        drone = VaspToDbTaskDrone(database="creator_unittest",
                                  simulate_mode=simulate)
        queen = BorgQueen(drone)
        queen.serial_assimilate(os.path.join(test_dir, 'db_test'))
        data = queen.get_data()
        self.assertEqual(len(data), 5)
        if not simulate:
            db = conn["creator_unittest"]
            data = db.tasks.find()
            self.assertEqual(data.count(), 5)
            warnings.warn("Actual db insertion mode.")

        for d in data:
            dir_name = d['dir_name']
            if dir_name.endswith("killed_mp_aflow"):
                self.assertEqual(d['state'], "killed")
                self.assertFalse(d['is_hubbard'])
                self.assertEqual(d['pretty_formula'], "SiO2")
            elif dir_name.endswith("stopped_mp_aflow"):
                self.assertEqual(d['state'], "stopped")
                self.assertEqual(d['pretty_formula'], "ThFe5P3")
            elif dir_name.endswith("sucess_mp_aflow"):
                self.assertEqual(d['state'], "successful")
                self.assertEqual(d['pretty_formula'], "TbZn(BO2)5")
                self.assertAlmostEqual(d['output']['final_energy'],
                                       -526.66747274, 4)
            elif dir_name.endswith("Li2O_aflow"):
                self.assertEqual(d['state'], "successful")
                self.assertEqual(d['pretty_formula'], "Li2O")
                self.assertAlmostEqual(d['output']['final_energy'],
                                       -14.31446494, 4)
                self.assertEqual(len(d["calculations"]), 2)
            elif dir_name.endswith("Li2O"):
                self.assertEqual(d['state'], "successful")
                self.assertEqual(d['pretty_formula'], "Li2O")
                self.assertAlmostEqual(d['output']['final_energy'],
                                       -14.31337758, 4)
                self.assertEqual(len(d["calculations"]), 1)

        if not simulate:
            conn.drop_database("creator_unittest")


if __name__ == "__main__":
    unittest.main()
