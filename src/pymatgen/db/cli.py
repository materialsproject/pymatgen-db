"""A helper script for many matgendb functions."""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import multiprocessing
import sys

from pymatgen.apps.borg.queen import BorgQueen
from pymatgen.db import (
    DEFAULT_SETTINGS,
    SETTINGS,
    DBConfig,
    MongoJSONEncoder,
    QueryEngine,
    VaspToDbTaskDrone,
    get_settings,
)
from pymongo import ASCENDING, MongoClient

_log = logging.getLogger("mg")  # parent


def init_db(args):
    """
    Initializes the database configuration and stores it in a specified configuration file.
    Prompts the user for configuration inputs with the ability to accept default values.

    Parameters:
        args (Namespace): Command line arguments namespace object. Should contain 'config_file',
        which specifies the target file to save configuration.

    Raises:
        FileNotFoundError: Raised if the specified config file cannot be created or written to.
        ValueError: Raised if the provided or default port value is not a valid integer.

    Notes:
        Default settings for the configuration values are prepopulated from DBConfig.ALL_SETTINGS
        and DEFAULT_SETTINGS.
    """
    settings = DBConfig.ALL_SETTINGS
    defaults = dict(DEFAULT_SETTINGS)
    doc = {}
    print("Please supply the following configuration values")
    print("(press Enter if you want to accept the defaults)\n")
    for k in settings:
        v = defaults.get(k, "")
        val = input(f"Enter {k} (default: {v}) : ")
        doc[k] = val if val else v
    doc["port"] = int(doc["port"])  # enforce the port as an int
    for k in ["admin_user", "admin_password", "readonly_user", "readonly_password"]:
        v = defaults.get(k, "")
        val = input(f"Enter {k} (default: {v}) : ")
        doc[k] = val if val else v
    with open(args.config_file, "w") as f:
        json.dump(doc, f, indent=4, sort_keys=True)
    print(f"\nConfiguration written to {args.config_file}!")


def update_db(args):
    """
    Update the database with computational task data based on the provided arguments.

    This function is responsible for configuring logging, extracting settings from the
    provided configuration file, and performing parallel database insertion of tasks
    from a specified directory. It utilizes multiprocessing for parallelism and supports
    overwriting duplicate records if specified.

    Arguments:
        args: argparse.Namespace
            A namespace object containing the following attributes:
            - logfile: Optional list containing a single logging file path (list[str])
            - config_file: Path to the configuration file (str)
            - author: Name of the author to include in the task (Optional[str])
            - tag: Tags to append to the tasks in the database (Optional[list[str]])
            - parse_dos: Boolean indicating whether to parse density of states (bool)
            - force_update_dupes: Boolean to indicate updating duplicates in the database (bool)
            - ncpus: Number of CPUs to use for parallel processing (Optional[int])
            - directory: Directory path with task data to assimilate (str)

    Supported types for attributes are either explicitly stated in the function's input
    or inferred through parameter type hints.
    """
    FORMAT = "%(relativeCreated)d msecs : %(message)s"

    if args.logfile:
        logging.basicConfig(level=logging.INFO, format=FORMAT, filename=args.logfile[0])
    else:
        logging.basicConfig(level=logging.INFO, format=FORMAT)

    d = get_settings(args.config_file)

    _log.info(f"Db insertion started at {datetime.datetime.now()}.")
    additional_fields = {"author": args.author, "tags": args.tag}
    drone = VaspToDbTaskDrone(
        host=d["host"],
        port=d["port"],
        database=d["database"],
        user=d["admin_user"],
        password=d["admin_password"],
        parse_dos=args.parse_dos,
        collection=d["collection"],
        update_duplicates=args.force_update_dupes,
        additional_fields=additional_fields,
        mapi_key=d.get("mapi_key", None),
    )
    ncpus = multiprocessing.cpu_count() if not args.ncpus else args.ncpus
    _log.info(f"Using {ncpus} cpus...")
    queen = BorgQueen(drone, number_of_drones=ncpus)
    queen.parallel_assimilate(args.directory)
    tids = list(map(int, filter(lambda x: x, queen.get_data())))
    _log.info(f"Db update completed at {datetime.datetime.now()}.")
    _log.info(f"{len(tids)} new task ids inserted.")


def optimize_indexes(args):
    """
    Optimize indexes for a MongoDB collection based on provided configuration.

    This function reads database settings from a configuration file, connects to
    the MongoDB instance, and modifies the indexes for a specified collection.
    It removes all existing indexes, creates a unique index on the "task_id" field,
    and builds indexes on a predefined set of fields. Additionally, it creates
    a compound index based on "nelements" and "elements".

    Parameters:
        args (argparse.Namespace): The arguments provided to the function,
            containing a "config_file" attribute that specifies the file path
            to read the database configuration.

    Raises:
        pymongo.errors.PyMongoError: If an error occurs while interacting with
            the MongoDB server.

    """
    d = get_settings(args.config_file)
    c = MongoClient(d["host"], d["port"])
    db = c[d["database"]]
    db.authenticate(d["admin_user"], d["admin_password"])
    coll = db[d["collection"]]
    coll.drop_indexes()
    coll.ensure_index("task_id", unique=True)
    for key in [
        "unit_cell_formula",
        "reduced_cell_formula",
        "chemsys",
        "nsites",
        "pretty_formula",
        "analysis.e_above_hull",
        "icsd_ids",
    ]:
        print(f"Building {key} index")
        coll.ensure_index(key)
    print("Building nelements and elements compound index")
    compound_index = [("nelements", ASCENDING), ("elements", ASCENDING)]
    coll.ensure_index(compound_index)
    coll.ensure_index(compound_index)


def query_db(args):
    """
    Query the database based on specified properties and criteria, and output the
    results in either JSON format or as a tabulated table. The function retrieves
    database connection settings, initializes a query engine, processes input
    parameters, and executes a query with the provided properties and criteria.

    Parameters:
        args: argparse.Namespace
            Command-line arguments containing configuration file path, query
            criteria, database properties, and output format options.

    Raises:
        SystemExit
            Raised when the specified criteria argument is not a valid JSON string.
    """
    from tabulate import tabulate

    d = get_settings(args.config_file)
    qe = QueryEngine(
        host=d["host"],
        port=d["port"],
        database=d["database"],
        user=d["readonly_user"],
        password=d["readonly_password"],
        collection=d["collection"],
        aliases_config=d.get("aliases_config", None),
    )
    criteria = None
    if args.criteria:
        try:
            criteria = json.loads(args.criteria)
        except ValueError:
            print(f"Criteria {args.criteria} is not a valid JSON string!")
            sys.exit(-1)

    # TODO: document this 'feature' --dang 4/4/2013
    def is_a_file(s):
        return len(s) == 1 and s[0].startswith(":")

    if is_a_file(args.properties):
        with open(args.properties[0][1:], "rb") as f:
            props = [s.strip() for s in f]
    else:
        props = args.properties

    if args.dump_json:
        for r in qe.query(properties=props, criteria=criteria):
            print(json.dumps(r, cls=MongoJSONEncoder))
    else:
        t = []
        for r in qe.query(properties=props, criteria=criteria):
            t.append([r[p] for p in props])
        print(tabulate(t, headers=props))


def main():
    """
    Main function for handling pymatgen-db management commands.

    This function serves as the entry point for the mgdb command line utility, which provides
    tools for database management, including inserting VASP calculation data, running queries,
    and initializing configurations. The main subcommands available are `init`, `insert`,
    `query`, and `optimize`.

    Summary:
    - `init`: Sets up an initial database configuration file.
    - `insert`: Inserts VASP calculation data from specified directory into the database.
    - `query`: Allows querying the database for specific properties or criteria.
    - `optimize`: Tools for optimizing database indexes.
    - Configuration options and verbosity levels can be specified globally for the commands.

    Subcommands:
    - init: Sets up an initial configuration file.
    - insert: Inserts calculation data into the database.
    - query: Queries the database for specified criteria and properties.
    - optimize: Optimizes database indexes.

    Raises:
    - SystemExit: In the case of argument parsing errors or invalid subcommands.

    Parameters:
    - None

    Returns:
    - None
    """
    db_file = SETTINGS.get("PMGDB_DB_FILE")
    parser = argparse.ArgumentParser(
        description="""
    mgdb is a complete command line db management script for pymatgen-db. It
    provides the facility to insert vasp runs, perform queries, and run a web
    server for exploring databases that you create. Type mgdb -h to see the
    various options.

    Author: Shyue Ping Ong
    Version: 3.0
    Last updated: Mar 23 2013"""
    )

    # Parents for all subparsers.
    parent_vb = argparse.ArgumentParser(add_help=False)
    parent_vb.add_argument("--quiet", "-q", dest="quiet", action="store_true", default=False, help="Minimal verbosity.")
    parent_vb.add_argument(
        "--verbose",
        "-v",
        dest="vb",
        action="count",
        default=0,
        help="Print more verbose messages to standard error. Repeatable. (default=ERROR)",
    )
    parent_cfg = argparse.ArgumentParser(add_help=False)
    parent_cfg.add_argument(
        "-c",
        "--config",
        dest="config_file",
        type=str,
        default=db_file,
        help="Config file to use. Generate one using mgdb "
        "init --config filename.json if necessary. "
        "Otherwise, the code searches for a db.json. If"
        "none is found, an no-authentication "
        "localhost:27017/vasp database and tasks "
        "collection is assumed.",
    )

    # change db_file to the default "db.json" if it does not exist
    db_file = db_file or "db.json"

    # Init for all subparsers.
    subparsers = parser.add_subparsers()

    # The 'init' subcommand.
    pinit = subparsers.add_parser("init", help="Initialization tools.", parents=[parent_vb])
    pinit.add_argument(
        "-c",
        "--config",
        dest="config_file",
        type=str,
        nargs="?",
        default=db_file,
        help="Creates an db config file for the database. Default filename is db.json.",
    )
    pinit.set_defaults(func=init_db)

    popt = subparsers.add_parser("optimize", help="Optimization tools.")

    popt.add_argument(
        "-c",
        "--config",
        dest="config_file",
        type=str,
        nargs="?",
        default=db_file,
        help="Creates an db config file for the database. Default filename is db.json.",
    )
    popt.set_defaults(func=optimize_indexes)

    # The 'insert' subcommand.
    pinsert = subparsers.add_parser("insert", help="Insert vasp runs.", parents=[parent_vb, parent_cfg])
    pinsert.add_argument("directory", metavar="directory", type=str, default=".", help="Root directory for runs.")
    pinsert.add_argument(
        "-l", "--logfile", dest="logfile", type=str, help="File to log db insertion. Defaults to stdout."
    )
    pinsert.add_argument(
        "-t",
        "--tag",
        dest="tag",
        type=str,
        nargs="+",
        default=[],
        help="Tag your runs for easier search. Accepts multiple space-separated tags. E.g., '--tag metal energy'",
    )
    pinsert.add_argument(
        "-f",
        "--force",
        dest="force_update_dupes",
        action="store_true",
        help="Force update duplicates. This forces the analyzer to reanalyze already inserted data.",
    )
    pinsert.add_argument("-d", "--parse_dos", dest="parse_dos", action="store_true", help="Whether to parse the dos.")
    pinsert.add_argument(
        "-a",
        "--author",
        dest="author",
        type=str,
        nargs=1,
        default=None,
        help="Enter a *unique* author field so that you can trace back what you ran.",
    )
    pinsert.add_argument(
        "-n",
        "--ncpus",
        dest="ncpus",
        type=int,
        default=None,
        help="Number of CPUs to use in inserting. If "
        "not specified, multiprocessing will use "
        "the number of cpus detected.",
    )
    pinsert.set_defaults(func=update_db)

    # The 'query' subcommand.
    pquery = subparsers.add_parser(
        "query", help="Query tools. Requires the use of pretty_table.", parents=[parent_vb, parent_cfg]
    )
    pquery.add_argument(
        "--crit",
        dest="criteria",
        type=str,
        default=None,
        help="Query criteria in typical json format. E.g., {'task_id': 1}.",
    )
    pquery.add_argument(
        "--props",
        dest="properties",
        type=str,
        default=[],
        nargs="+",
        required=True,
        help="Desired properties. Repeatable. E.g., pretty_formula, task_id, energy...",
    )
    pquery.add_argument(
        "--dump",
        dest="dump_json",
        action="store_true",
        default=False,
        help="Simply dump results to JSON instead of a tabular view",
    )
    pquery.set_defaults(func=query_db)

    # Parse args
    args = parser.parse_args()

    # Run appropriate subparser function.
    args.func(args)
