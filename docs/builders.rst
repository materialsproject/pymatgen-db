.. _builders:

Materials Project "Builders"
============================

The Materials Project relies on MongoDB databases. The process of creating these
databases from either files or other MongoDB databases is encapsulated in
the "builders" subpackage. The point of the builders is to automate and
simplify the process of creating databases; an important sub-goal is to provide
mechanisms for making building more efficient.

Contents:

* :ref:`bld-writing`
* :ref:`bld-running`

.. _bld-writing:

Writing a builder
=================

To write a builder, you must create a Python class that inherits from
`matgendb.builders.core.Builder`
(see the :doc:`matgendb.builders <matgendb.builders>` package)
and implement a few methods on this class
to perform the specific work for your builder. In this section we will
give two example builders: a simple :ref:`FileCounter <bld-ex-filecounter>` builder
that just counts the lines in a file,
and a :ref:`CopyBuilder <bld-ex-copy>` that copies a MongoDB collection.

.. _bld-ex-filecounter:

Simple "FileCounter" builder
----------------------------

The first builder simply reads from a file, and counts the lines in that file.
In this section we'll show the whole program, then walk through it one section
at a time::

    from matgendb.builders.core import Builder
    class FileCounter(Builder):
        """Count lines and characters in a file.
        """
        def __init__(self, **kwargs):
            self.num_lines = 0
            Builder.__init__(self, **kwargs)

        def get_parameters(self):
            return {'input_file': {'type': 'str', 'desc': 'Input file path'}}

        def get_items(self, input_file=None):
            with open(input_file, "r") as f:
                for line in f:
                    yield line

        def process_item(self, item):
            self.num_lines += 1

        def finalize(self, errors):
            print("{:d} lines, {:d} characters".format(
                self.num_lines, self.num_chars))
            return True

**Initialization**::

    from matgendb.builders.core import Builder
    class FileCounter(Builder):
        """Count lines and characters in a file.
        """
        def __init__(self, **kwargs):
            self.num_lines = 0
            Builder.__init__(self, **kwargs)

The class inherits from the ``matgendb.core.Builder`` class. In this case, it includes
a constructor, but this is optional and often not needed. The constructor
simply initializes the number of lines counter and then calls its parent.

**get_parameters**::

         def get_parameters(self):
            return {'input_file': {'type': 'str', 'desc': 'Input file path'}}

This method returns a dictionary of metadata about the
parameters for ``get_items()``.
This metadata is used when running a builder with the `mgbuild` program.
More details on this are given in :ref:`bld-running`.
For now, it is enough to note that the
parameters must match the keyword arguments to ``get_items()``, both in
name and (expected) type.

**get_items**::

        def get_items(self, input_file=None):
            with open(input_file, "r") as f:
                for line in f:
                    yield line


The two main methods that you **must** override are called ``get_items()`` and
``process_item()``. The first will return an iterator, in this case
the function simply returns one line of the file at a time.
Notice that you can make the function into a generator by using ``yield`` to
return items, but returning any other iterable would also work fine (e.g. the
function could have been a one-liner "return open(input_file).readlines()").

**process_item**::

        def process_item(self, item):
            self.num_lines += 1

Here the instance variable ``num_lines`` is simply incremented for every
line passed to it by the ``get_items()`` iterator.

.. warning::

    Updating instance variables
    will cause improper behavior if the user runs the builder in parallel.
    This occurs because the parallel mode automatically starts multiple
    copies of the same class, and their independent actions will clash.
    If you really need to update some shared state,
    use the Python `multiprocessing` module functions.
    See the `multiprocessing docs
    <https://docs.python.org/2/library/multiprocessing.html>`_
    for details.

**finalize**::

        def finalize(self, errors):
            print("{:d} lines, {:d} characters".format(
                self.num_lines, self.num_chars))
            return True

Optionally, you can put code that will be run once (for all builders) in
the ``finalize()`` method. Here we just print a result.
The return value of finalize is used to determine whether the build was
successful. So make sure you return ``True``, if it succeeds, since the default
of None will read as ``False``.

Note that this builder did not access MongoDB in any way.
The next example will show MongoDB access and other features.

.. _bld-ex-copy:

Database "CopyBuilder"
-----------------------

The next builder does a simple DB operation: copying one MongoDB collection
from a source to a destination. As before, we begin with the full program
and then step through it one snippet at at time::

    from matgendb.builders import core, util
    from matgendb.query_engine import QueryEngine

    _log = util.get_builder_log("copy")

    class CopyBuilder(core.Builder):
        """Copy from one MongoDB collection to another.
        """
        def __init__(self, *args, **kwargs):
            self._target_coll = None
            core.Builder.__init__(self, *args, **kwargs)

        def get_items(self, source=None, target=None, crit=None):
            """Copy records from source to target collection.

            :param source: Input collection
            :type source: QueryEngine
            :param target: Output collection
            :type target: QueryEngine
            :param crit: Filter criteria, e.g. "{ 'flag': True }".
            :type crit: dict
            """
            self._target_coll = target.collection
            if not crit:  # reduce any False-y crit value to None
                crit = None
            cur = source.query(criteria=crit)
            _log.info("copy: source={} crit={} count={:d}"
                      .format(source.collection, crit, len(cur)))
            return cur

        def process_item(self, item):
            self._target_coll.insert(item)

**Logging**::

    _log = util.get_builder_log("copy")

In this program, we start by setting up logging.
For convenience, the ``util.get_builder_log()`` method creates a new
Python logging.Logger instance with a standard name and format.

**Initialization**::

    def __init__(self, *args, **kwargs):
        self._target_coll = None
        core.Builder.__init__(self, *args, **kwargs)

When we initialize the class, we create an instance variable that we will
later use to remember the target collection.

**get_items**::

        def get_items(self, source=None, target=None, crit=None):
            """Copy records from source to target collection.

            :param source: Input collection
            :type source: QueryEngine
            :param target: Output collection
            :type target: QueryEngine
            :param crit: Filter criteria, e.g. "{ 'flag': True }".
            :type crit: dict
            """
            self._target_coll = target.collection
            if not crit:  # reduce any False-y crit value to None
                crit = None
            cur = source.query(criteria=crit)
            _log.info("source={} crit={} count={:d}"
                      .format(source.collection, crit, len(cur)))
            return cur

For a copy operation, the ``get_items()`` method must query the source
collection and get an iterator over the records.

There are two things that are different from the FileCounter example.
First, note that there is no ``get_parameters()`` method at all. Instead
the *docstring* of this method is actually a machine-readable version of
the metadata needed for running the builder. Not coincidentally, the format
expected by this docstring is also understood by Sphinx's autodoc feature.
This way, you will be able to kill two birds with one stone: your builders
will be documented for command-line invocation, and you can easily generate
HTML, PDF, etc. documentation pages.

Second, this method connects to the database and queries it. But, you may
be asking, where is the ``db.connect()`` call? This is handled by some magic
that is in the docstring. Notice that the type of both the source and
target is ``QueryEngine``. This is a special datatype that instructs the
driver program (`mgbuild`) to expect a database configuration file with
host name, user, password, database name, etc. and to automatically connect
to this database and return a ``matgendb.query_engine.QueryEngine`` instance.
These instances are passed in as arguments to the method. So, all the
method has to do is to use the QueryEngine object. In this case,
this means creating a cursor that iterates over the source collection
and remembering the target collection in an instance variable.

.. note::

    Unlike the previous example where instance variables might cause
    strange behavior, here the ``_target_coll`` instance variable is
    perfectly fine for parallel execution because the individual
    builder instances do not want to share the state of this variable
    between them -- they each want and need their own copy.

**process_item**::

        def process_item(self, item):
            self._target_coll.insert(item)

Here, we simply insert every item into the target collection.

As we will see later, the builder framework also contains some automatic
functionality for *incremental* building, which means only looking at
records that are new since the last time. Usually this involves some extra
logic inside the builder itself, but in a very simple case like this
the copying would automatically work with the incremental mode.

.. _bld-running:

Running a builder
=================

This section describes how,
once you have written a builder class, you can use `mgbuild` to run
it, possibly in parallel and possibly "incrementally", on some inputs.

We will break this process into two parts:

* :ref:`Displaying <bld-run-show>` the usage for a given builder class
* :ref:`Running <bld-run-exe>` the builder

Both of these use the `mgbuild` sub-command "run" (alternatively: "build"),
like this::

    mgbuild run <arguments>

In the examples below, we will assume that you have pymatgen-db installed and
in your Python path. We will use the example modules that are installed
in ``matgendb.builders.examples``.

.. _bld-run-show:

Displaying builder usage
-------------------------

You can get the list of parameters and their types for a given builder
by giving its full module path, and the ``-u`` or ``--usage`` option::

    % mgbuild run -u matgendb.builders.examples.copy_builder.CopyBuilder

    matgendb.builders.examples.copy_builder.CopyBuilder
      Copy from one MongoDB collection to another.
      Parameters:
        crit (dict): Filter criteria, e.g. "{ 'flag': True }".
        source (QueryEngine): Input collection
        target (QueryEngine): Output collection

.. note::

    You will also get the usage information if you invoke the builder with the
    wrong number of arguments (e.g. zero), although in this case you will also
    see some error messages.

.. _bld-run-exe:

Running the builder
--------------------

The usage of the `mgbuild run` command is as follows::

    usage: mgbuild run [-h] [--quiet] [--verbose] [-i OPER[:FIELD]] [-n NUM_CORES]
                       [-u]
                       builder [parameter [parameter ...]]

    positional arguments:
      builder               Builder class, relative or absolute import path, e.g.
                            'my.awesome.BigBuilder' or 'BigBuilder'.
      parameter             Builder parameters, in format <name>=<value>. If the
                            parameter type is QueryEngine, the value should be a
                            JSON configuration file. Prefix filename with a '-' to
                            ignore incremental mode for this QueryEngine.

    optional arguments:
      -h, --help            show this help message and exit
      --quiet, -q           Minimal verbosity.
      --verbose, -v         Print more verbose messages to standard error.
                            Repeatable. (default=ERROR)
      -i OPER[:FIELD], --incr OPER[:FIELD]
                            Incremental mode for operation and optional sort-field
                            name. OPER may be one of: copy, other, build. Default
                            FIELD is '_id'
      -n NUM_CORES, --ncores NUM_CORES
                            Number of cores or processes to run in parallel (1)
      -u, --usage           Print usage information on selected builder and exit.


To run the builder, you need at a minimum to give the full path to the
builder class, and then values for each parameter. There are also optional
arguments for building in parallel and building incrementally. This section will
walk through from simple to more complex examples.

Basic usage
^^^^^^^^^^^

Run the copy builder::

     mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
         source=conf/test1.json target=conf/test2.json crit='{}'

In this example, we are running the CopyBuilder with configuration files
for the source and target and empty criteria (i.e. copy everything). The
copy will be run in a single thread.

The configuration files in question are just JSON files that look like this
(you could add "user" and "password" for authenticated DBs)::

    {"host": "localhost", "port": 27017,
     "database": "foo", "collection": "test1"}

Running in parallel
^^^^^^^^^^^^^^^^^^^^

Most machines have multiple cores, and hundreds of cores will be common
in the near future. If your item processing requires any
real work, you will probably benefit by running in parallel::

     mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
         source=conf/test1.json target=conf/test2.json crit='{}' -n 8

The same command as previously, but with **-n 8** added to cause 8 parallel
threads to be spawned to run the copy in parallel.

.. note::

    For parallel runs, only the ``process_item()`` method is run in parallel.
    The ``get_items()`` is always run sequentially.

Incremental builds
^^^^^^^^^^^^^^^^^^

Incremental building allows successive builds of source MongoDB collection(s)
to only operate on the records added since the last build. This can save
huge amounts of time. A cartoon of the difference between an incremental and
full (non-incremental) build is shown below.

.. image:: _static/incremental_build.png

Incremental building
is controlled by the ``-i/--incr`` option.
What this really does is to add some behind-the-scenes bookkeeping for every
parameter of type ``QueryEngine`` (except ones where it is explicitly
turned off, :ref:`see below <bld-incr-skip>`) that records and retrieves the spot where processing
was last ended. Multiple spots are allowed per-collection by requiring an
"operation". Currently,
only a small set of operations are allowed: "copy", "build", and "other".

For incremental building to work properly, there must be some field
in the collection that increases monotonically. This field is used to
determine which records come *after* the spot marked on the last run. By
default this field is `_id`, but it is highly recommended to choose a
collection-specific identifier because `_id` as chosen by the
client is not always monotonic.

**Basic incremental build**::

    mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
        source=conf/test1.json target=conf/test2.json crit='{}' \
        -i copy

Copies from source to target. Subsequent runs will only copy records that
are newer (according to the field, in this case defaulting to ``_id``)
than the last record from the previous run.

**Incremental build with parallelism**::

    mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
        source=conf/test1.json target=conf/test2.json crit='{}' \
        -n 8 -i copy

Parallelism is not different with incremental builds. As before, we
simply add **-n 8** to the command-line.

**Incremental build with custom identifier**::

    mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
        source=conf/test1.json target=conf/test2.json crit='{}' \
        -i copy:num

This example runs an incremental build with the "copy" operation,
using the ``num`` field instead of the default ``_id``.

.. _bld-incr-skip:

**Incremental build skipped for some collections**::

    mgbuild run  matgendb.builders.examples.copy_builder.CopyBuilder \
        source=conf/test1.json target=-conf/test2.json crit='{}' \
        -i copy:num

This is pretty subtle: notice the "-" inserted after the "=" in
``target=-conf/test2.json``. This has the effect of not adding tracking information
for the target collection.
In this case, tracking the last record added to the target
isn't useful for the copy, all that matters is knowing where we stopped
in the source collection.