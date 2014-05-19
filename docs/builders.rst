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
`matgendb.builders.core.Builder` and implement a few methods on this class
to perform the specific work for your builder. In this section we will
give two example builders: a simple `FileCounter <bld-ex-filecounter>`_ builder
that just counts the lines in a file,
and a `CopyBuilder <bld-ex-copy>`_ that copies a MongoDB collection.

.. _bld-ex-filecounter::

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

In the first section, we have the class declaration and initialization::

    from matgendb.builders.core import Builder
    class FileCounter(Builder):
        """Count lines and characters in a file.
        """
        def __init__(self, **kwargs):
            self.num_lines = 0
            Builder.__init__(self, **kwargs)

The class inherits from the matgendb `Builder` class. In this case, it includes
a constructor, but this is optional and often not needed. The constructor
simply initializes the number of lines counter and then calls its parent.

Next, we have a the method `get_parameters()`::

         def get_parameters(self):
            return {'input_file': {'type': 'str', 'desc': 'Input file path'}}

This method is used to provide metadata about how to run
this builder to the `mgbuild` program. More details on this are given in
:ref:`bld-running`. For now, it is enough to note that the
parameters must match the keyword arguments to `get_items`, both in
name and type.

The two main methods that you _must_ override are called `get_items` and
`process_item`. The first will return an iterator, and each item returned
by that iterator is fed to the second. Here, we see the `get_items` for our
line counter::

        def get_items(self, input_file=None):
            with open(input_file, "r") as f:
                for line in f:
                    yield line

The function simply returns one line of the file at a time.
Notice that you can make the function into a generator by using `yield` to
return items, but returning any other iterable would also work fine (e.g. the
function could have been a one-liner "return open(input_file).readlines()").

Each item returned is then processed::

        def process_item(self, item):
            self.num_lines += 1

Here the instance variable `num_lines` is simply incremented.

.. warning::

    Using instance variables directly like this
    will cause improper behavior if the user runs the builder in parallel.
    This occurs because the parallel mode automatically starts multiple
    copies of the same class, and they do not share the same instance variables.
    Instead, use the Python `multiprocessing` module functions to share
    state between processes. See the `multiprocessing docs
    <https://docs.python.org/2/library/multiprocessing.html>`_
    for details.

Optionally, you can put code that will be run once (for all builders) in
the `finalize` method. Here we just print a result::

        def finalize(self, errors):
            print("{:d} lines, {:d} characters".format(
                self.num_lines, self.num_chars))
            return True

The return value of finalize is used to determine whether the build was
successful. So make sure you return `True`, if it succeeds, since the default
of None will read as False.

Note that this builder did not access MongoDB in any way. This is not a
requirement of builders, though it is certainly the main reason for using this
framework. The next example will show MongoDB access and other features.

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

In this program, we start by setting up logging::

    _log = util.get_builder_log("copy")

For convenience, the `util` module has a method `get_builder_log()`
that creates a new Python logging.Logger instance with a standard name and
format.

When we initialize the class, we create an instance variable that we will
later use to remember the target collection::

    def __init__(self, *args, **kwargs):
        self._target_coll = None
        core.Builder.__init__(self, *args, **kwargs)

For a copy operation, the `get_items` method must query the source
collection and get an iterator over the records::

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

There are two things that are different from the FileCounter example.
First, note that there is no `get_parameters` method at all. Instead
the _docstring_ of this method is actually a machine-readable version of
the metadata needed for running the builder. Not coincidentally, the format
expected by this docstring is also understood by Sphinx's autodoc feature.
This way, you will be able to kill two birds with one stone: your builders
will be documented for command-line invocation, and you can easily generate
HTML, PDF, etc. documentation pages.

Second, this method connects to the database and queries it. But, you may
be asking, where is the `db.connect()` call? This is handled by some magic
that is in the docstring. Notice that the type of both the source and
target is `QueryEngine`. This is a special datatype that instructs the
driver program (`mgbuild`) to expect a database configuration file with
host name, user, password, database name, etc. and to automatically connect
to this database and return a `matgendb.query_engine.QueryEngine` instance.
These instances are passed in as arguments to the method. So, all the
method has to do is to use the QueryEngine object. In this case,
this means creating a cursor that iterates over the source collection
and remembering the target collection in an instance variable.

.. note::

    Unlike the previous example where instance variables might cause
    strange behavior, here the `_target_coll` instance variable is
    perfectly fine for parallel execution because the individual
    builder instances do not want to share the state of this variable
    between them -- they each want and need their own copy.

All that is left for the copy operation is to insert every item into the
target collection::

        def process_item(self, item):
            self._target_coll.insert(item)

As we will see later, the builder framework also contains some automatic
functionality for _incremental_ building, which means only looking at
records that are new since the last time. Usually this involves some extra
logic inside the builder itself, but in a very simple case like this
the copying would automatically work with the incremental mode.

.. _bld-running:

Running a builder
=================
