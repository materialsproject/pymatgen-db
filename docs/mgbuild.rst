.. _mgbuild:

Materials Project Database Builder: mgbuild
============================================

The `mgbuild` program is used to build derived databases from the `tasks` collection. The program has two main modes, "merge" and "vasp", which will both be described below.

Example
--------

If you have a sandbox database that you want to build against the main database, you need to start with the `merge` subcommand. For example:

    mgbuild merge -n output -c db.json -s sandbox.json 

In this example the resulting database will be called `output.tasks.merged`. The `db.json` and `sandbox.json` files tell `mgbuild` how to connect to the databases.

After you have all your tasks in the same database, run the `vasp` subcommand to build the derived collections.

    mgbuild -m -c db.json

The `-m` flag is used to indicate that the collection was merged by `mgbuild merge` and the `db.json` file is the same connection information as before. 

The rest of this section will give more detailed usage information.

`mgbuild` usage
---------------

The main mgbuild command just presents a menu of the subcommands.

    usage: mgbuild.py [-h] {vasp,merge} ...

    Build sandboxes and derived collections

    optional arguments:
      -h, --help    show this help message and exit

    subcommands:
      Actions

    {merge,list,build}
        merge_             Merge sandbox and core database
        list_              list builders
        build_             run a builder

.. _merge:

`mgbuild merge` usage
----------------------

The merge command merges a task collection from a sandbox into a new collection in the main database.

    usage: mgbuild.py merge [-h] [-c FILE] [-p PREFIX] [--verbose] [-P NUM_CORES]
                            [-n NAME] [-s FILE] [-W]

    optional arguments:
      -h, --help            show this help message and exit
      -c FILE, --config FILE
                            Configure database connection from FILE (db.json)
      -p PREFIX, --prefix PREFIX
                            Collection name prefix, ie namespace
      --verbose, -v         Print more verbose messages to standard error.
                            Repeatable. (default=ERROR)
      -P NUM_CORES, --ncores NUM_CORES
                            Number of cores, thus number of threads to runin
                            parallel (16)
      -n NAME, --name NAME  Sandbox name, for prefixing merged task IDs. If not
                            given, try to use -p/--prefix, then default (sandbox)
      -s FILE, --sandbox FILE
                            Configure sandbox database from FILE (required)
      -W, --wipe            Wipe target collection, removing all data in it,
                            before merge

The connections are configured with JSON files that are in the same format as pymatgen-db and look like this:

    $ cat db.json 
    {"host": "localhost",
    "port": 27017,
    "database": "mg_core_dev"
    }

    $ cat sandbox.json
    {"host": "localhost",
    "port": 27017,
    "database": "mg_sandbox_dev"
    }

These files would be the arguments to `-c` and `-s`.

The target output collection will be in the "sandbox" database and it will have the name [<prefix>].tasks.merged, where <prefix> is the value of `-n/--name`.

.. _build:

`mgbuild build` usage
---------------------

The "build" command builds the set of derived collections from the electronic structure information in the "tasks" collection.

usage: mgbuild build [-h] [--quiet] [--verbose] [-b NAME] [-i]
                     [--incr-op INCR_OP] [--incr-field INCR_FIELD] [-C DIR]
                     [-k KEYWORDS] [-m MODULE] [-n NUM_CORES] [-p PREFIX]

optional arguments:
  -h, --help            show this help message and exit
  --quiet, -q           Minimal verbosity.
  --verbose, -v         Print more verbose messages to standard error.
                        Repeatable. (default=ERROR)
  -b NAME, --builder NAME
                        Run builder NAME, which is relative to the module path
                        in -m/--module
  -i, --incr            Incremental mode, only build from new values in
                        source. See also: --incr-op and --incr-field.
  --incr-op INCR_OP     Operation name for incremental mode: *copy, other,
                        build
  --incr-field INCR_FIELD
                        Field to sort on for incremental mode (_id)
  -C DIR, --config-path DIR
                        Configure database connection from .json files in DIR
                        (default=.)
  -k KEYWORDS, --kvp KEYWORDS
                        Key/value pairs, in format <key>=<value>, passed to
                        builder function. For QueryEngine arguments, the value
                        should be the name of a DB configuration file,
                        relative to the path given by -C/--config-path,
                        without the '.json' suffix; if not given, a
                        configuration file '<key>.json' will be assumed.
  -m MODULE, --module MODULE
                        Find builder modules under MODULE
                        (default=matgendb.builders)
  -n NUM_CORES, --ncores NUM_CORES
                        Number of cores or processes to run in parallel (16)
  -p PREFIX, --prefix PREFIX
                        Collection name prefix for input (and possibly output)
                        collections

.. _list:

`mgbuild list` usage
---------------------

The list command shows avaiable `builder` modules under a given path.

    usage: mgbuild list [-h] [--quiet] [--verbose] [-m MODULE]

    optional arguments:
      -h, --help            show this help message and exit
      --quiet, -q           Minimal verbosity.
      --verbose, -v         Print more verbose messages to standard error.
                            Repeatable. (default=ERROR)
      -m MODULE, --module MODULE
                            Find builder modules under MODULE
                            (default=matgendb.builders)


.. _builderAPI:

Builder API
===========

.. currentmodule:: matgendb.builders

.. autoclass:: Builder


