#!/usr/bin/env python


"""
A master convenience script with many tools for vasp and structure analysis.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "1.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Dec 1, 2012"

import datetime
import logging
from matgendb.creator import VaspToDbTaskDrone
from pymatgen.apps.borg.queen import BorgQueen
import multiprocessing


logger = logging.getLogger(__name__)


def parallel_update_db(args):
    logger.info("Db insertion started at {}.".format(datetime.datetime.now()))
    additional_fields = {"author": args.author, "tags": args.tag}
    drone = VaspToDbTaskDrone(
        host=args.host, port=args.port,  database=args.db, user=args.user,
        password=args.password, parse_dos=False, collection=args.collection,
        update_duplicates=args.force_update_dupes,
        additional_fields=additional_fields)
    ncpus = multiprocessing.cpu_count()
    queen = BorgQueen(drone, number_of_drones=ncpus)
    queen.parallel_assimilate(args.directory)
    tids = map(int, filter(lambda x: x, queen.get_data()))
    logger.info("Db upate completed at {}.".format(datetime.datetime.now()))
    logger.info("{} new task ids inserted.".format(len(tids)))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="""
    Command line db insertion script.

    Author: Shyue Ping Ong
    Version: 2.0
    Last updated: Jun 21 2012""")
    parser.add_argument("directory", metavar="directory", type=str, default=".",
                        help="Root directory for runs.")
    parser.add_argument("-d", "--host", dest="host", type=str,
                        default=["localhost"],
                        help="Hostname of db. Defaults to \"localhost\".")
    parser.add_argument("-o", "--port", dest="port", type=int,
                        default=27017,
                        help="Port for DB. Defaults to 27017.")
    parser.add_argument("-b", "--database", dest="db", type=str,
                        default="vasp",
                        help="DB name. Defaults to \"vasp\".")
    parser.add_argument("-u", "--user", dest="user", type=str, default=None,
                        help="Admin username. Defaults to None.")
    parser.add_argument("-p", "--password", dest="password", type=str,
                        help="Admin password.")
    parser.add_argument("-c", "--collection", dest="collection", type=str,
                        default="tasks",
                        help="Collection name. Defaults to \"tasks\".")
    parser.add_argument("-l", "--logfile", dest="logfile", type=str,
                        help="File to log db insertion. Defaults to stdout.")
    parser.add_argument("-t", "--tag", dest="tag", type=str, nargs=1,
                        default=[],
                        help="Tag your runs for easier search."
                             " Accepts multiple tags")
    parser.add_argument("-f", "--force", dest="force_update_dupes",
                        action="store_true",
                        help="Force update duplicates. This forces the "
                             "analyzer to reanalyze already inserted data.")
    parser.add_argument("-a", "--author", dest="author", type=str, nargs=1,
                        default=None,
                        help="Enter a *unique* author field so that you can "
                             "trace back what you ran.")
    args = parser.parse_args()

    FORMAT = "%(relativeCreated)d msecs : %(message)s"

    if args.logfile:
        logging.basicConfig(level=logging.INFO, format=FORMAT,
                            filename=args.logfile[0])
    else:
        logging.basicConfig(level=logging.INFO, format=FORMAT)

    parallel_update_db(args)
