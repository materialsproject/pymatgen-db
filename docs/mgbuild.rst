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

      {vasp,merge}
        vasp        Build VASP derived collections
        merge       Merge sandbox and core database

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

`mgbuild vasp` usage
---------------------

The "vasp" command builds the set of derived collections from the electronic structure information in the "tasks" collection.

    usage: mgbuild.py vasp [-h] [-c FILE] [-p PREFIX] [--verbose] [-P NUM_CORES] [-m]

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
      -m, --merged          Use merged tasks collection with suffix merged, as
                            created by the 'merge' command for sandboxes

.. _builderAPI:

Builder API
===========

.. currentmodule:: matgendb.builders

.. autoclass:: Builder


