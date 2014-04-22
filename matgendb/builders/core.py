"""
Shared code for builders.

For developers implementing a new builder,
you should inherit from :class:`Builder`.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '5/29/13'

## Imports

# system
from abc import ABCMeta, abstractmethod
import copy
import logging
import Queue
import threading
import multiprocessing
# local
from matgendb.builders import schema
from matgendb import util as dbutil

## Logging

_log = logging.getLogger("mg.builders.shared")

## Exceptions


class BuildError(Exception):
    def __init__(self, who, why):
        errmsg = "Builder {} failed: {}".format(who, why)
        Exception.__init__(self, errmsg)

## Versioning (experimental)

DB_VERSION = 1

## Functions


def parse_fn_docstring(fn):
    """Get parameter and return types from function's docstring.

    Docstrings must use this format::

       :param foo: What is foo
       :type foo: int
       :return: What is returned
       :rtype: double

    :return: A pair (parameters, output), a map of names, each with keys 'type' and 'desc'.
    :rtype: tuple(dict)
    """
    doc = fn.__doc__
    params, return_ = {}, {}
    param_order = []
    for line in doc.split("\n"):
        line = line.strip()
        if line.startswith(":param"):
            _, name, desc = line.split(":", 2)
            name = name[6:].strip()  # skip 'param '
            params[name] = {'desc': desc.strip()}
            param_order.append(name)
        elif line.startswith(":type"):
            _, name, desc = line.split(":", 2)
            name = name[5:].strip()  # skip 'type '
            if not name in params:
                raise ValueError("'type' without 'param' for {}".format(name))
            params[name]['type'] = desc.strip()
        elif line.startswith(":return"):
            _1, _2, desc = line.split(":", 2)
            return_['desc'] = desc
        elif line.startswith(":rtype"):
            _1, _2, desc = line.split(":", 2)
            return_['type'] = desc.strip()
    return params, return_


## Classes


class Collections(object):
    """Interface to normalized names for collections.
    
    After initialization with a MongoDB database and optional parameters,
    you can access collections in `known_collections` as attributes.
    """
    #: Collection names that are accessible as attributes
    #: of an instance of this class
    known_collections = [
        'tasks', 'materials', 'diffraction_patterns',
        'electrodes', 'conversion_electrodes', 'bandstructures', 'icsd',
        'phase_diagrams', 'brototypes', 'electronic_structure']

    MIN_VER = 1
    MAX_VER = 1

    def __init__(self, db, version=1, prefix=None, task_suffix=None):
        """Set collections from database.

        :param db: MongoDB database, but really anything that acts like a dict. If None, it will be ignored.
        :type db: dict-like object
        :param version: Version of naming scheme for the collections
        :type version: int
        :param prefix: Prefix string to put before collection names, e.g. "dahn". Full
                       collection name will be <prefix>.<name>; don't include '.' in the input.
        :type prefix: str
        :param task_suffix: Add this suffix to the tasks collection. Used for merged collections for sandboxes.
        :type task_suffix: str
        :raise: ValueError if `version` is not known
        """
        if not self.MIN_VER <= version <= self.MAX_VER:
            raise ValueError("Bad version ({v:d}) not in range {v0} .. {v1} ".
                             format(v=version, v0=self.MIN_VER, v1=self.MAX_VER))
        self._names, self._coll = {}, {}
        if version == 1:
            for name in self.known_collections:
                full_name = "{}.{}".format(prefix, name) if prefix else name
                if name == 'tasks' and task_suffix is not None:
                    full_name = "{}.{}".format(full_name, task_suffix)
                self._names[name] = full_name
                self._coll[full_name] = None
        if db is None:
            self._db = dict.fromkeys(self.known_collections, 1)
        else:
            self._db = db
        self._prefix = prefix

    def __getattr__(self, item):
        if item in self._names:
            coll_name = self._names[item]
            coll = self._coll[coll_name]
            if coll is None:
                self._coll[coll_name] = coll = self._db[coll_name]
            return coll
        return self.__dict__[item]

    def get_collection_name(self, alias):
        return self._names[alias]

    @property
    def database(self):
        """Return the current database object.
        
        :return: Current database object
        """
        return self._db


def merge_tasks(core_collections, sandbox_collections, id_prefix, new_tasks, batch_size=100, wipe=False):
    """Merge core and sandbox collections into a temporary collection in the sandbox.

    :param core_collections: Core collection info
    :type core_collections: Collections
    :param sandbox_collections: Sandbox collection info
    :type sandbox_collections: Collections
    """
    merged = copy.copy(sandbox_collections)
    # create/clear target collection
    target = merged.database[new_tasks]
    if wipe:
        _log.debug("merge_tasks.wipe.begin")
        target.remove()
        merged.database['counter'].remove()
        _log.debug("merge_tasks.wipe.end")
    # perform the merge
    batch = []
    for doc in core_collections.tasks.find():
        batch.append(doc)
        if len(batch) == batch_size:
            target.insert(batch)
            batch = []
    if batch:
        target.insert(batch)
    batch = []
    for doc in sandbox_collections.tasks.find():
        doc['task_id'] = id_prefix + '-' + str(doc['task_id'])
        batch.append(doc)
        if len(batch) == batch_size:
            target.insert(batch)
            batch = []
    if batch:
        target.insert(batch)


class HasExamples(object):
    """Mix-in class for checking the output of a builder.

    This is a way to get some static checking of the schema of inserted documents,
    without imposing the burden of schema-checking every single document.
    The check is static in the sense that it will only be run by the unit tests.

     See the
    `pymatpro.db.builders.test.test_porous_builder` module for an example of
    how to use this to perform unit tests.
    """

    def examples(self):
        """Return example document(s) for collection(s).

        This must be implemented in subclasses.

        :return: List of pairs (doc, collection_name)
        :rtype: list(dict,str)
        """
        raise NotImplementedError()


    def validate_examples(self, fail_fn):
        """Check the examples against the schema.

        :param fail_fn: Pass failure messages to this function
        :type fail_fn: function(str)
        """
        for collection, doc in self.examples():
            _log.debug("validating example in collection {}".format(collection))
            sch = schema.get_schema(collection)  # with more err. checking
            result = sch.validate(doc)
            _log.debug("validation result: {}".format("OK" if result is None else result))
            if result is not None:
                fail_fn("Failed to validate sample document: {}".format(result))


class Builder(object):
    """Abstract base class for all builders

    To implement a new builder, inherit from this class and
    define the :meth:`setup` and :meth:`process_item` methods.
    It is important to add special "docstring" comments in the :meth:`setup`
    method, so the command-line program "mgbuild" can allow users to set them.
    See the documentation of the methods for more details.

    Here is a trivial example::

        class MyBuilder(Builder):
            def setup(self, n):
                '''My setup.

                :param n: Number of items
                :type n: int
                '''
                return list(range(n))

            def process_item(self, item):
                '''Process an item.
                '''
                print("processing item: {}".format(item))


    Although you will most likely not need to run these builders programmatically,
    if you do then this is an example of how to create and run::

        b = MyBuilder(ncores=1)
        b.run()
    """
    __metaclass__ = ABCMeta

    def __init__(self, ncores=0, threads=False, config=None):
        """Create new builder for threaded or multiprocess execution.

        :param ncores: Desired number of threads or processes to run
        :type ncores: int
        :param threads: Use threads (True) or processes (False)
        :type threads: bool
        :param config: If given, automatically connect to database using `connect` method.
                       You can access the connection with the attribute 'conn'.
        :type config: None, str, dict
        :raise: ValueError for bad 'config' arg
        """
        self._ncores = ncores if ncores else 15
        self._threaded = threads
        if threads:
            self._queue = Queue.Queue()
            self._states_lock = threading.Lock()
            self._run_parallel_fn = self._run_parallel_threaded
        else:
            self._queue = multiprocessing.Queue()
            self._run_parallel_fn = self._run_parallel_multiprocess
        self._status = BuilderStatus(ncores, is_threaded=threads)
        # connect, if config is given
        self.conn = self.connect(config) if config else None

    # ----------------------------
    # Override these in subclasses
    # ----------------------------

    @abstractmethod
    def setup(self, *args):
        """Perform one-time setup at the top of a run, returning
        an iterator on items to use as input.

        The parameters for this method are translated into command-line options
        for the command-line driver program (mgbuild). These parameters *must* be documented
        in special form in the 'docstring' at the top of the function. For example::

            class MyBuilder(Builder):
                def setup(self, source, target):
                '''
                :param source: The input porous materials collection
                :type source: QueryEngine
                :param target: The output materials collection
                :type target: QueryEngine
                '''

        If the type of the argument is 'QueryEngine', then the driver program will
        add options for, and create, a matgendb.query_engine.QueryEngine instance.
        The value given for this argument will be interpreted as the MongoDB collection name.

        :return: iterator
        """
        return [{"Hello": 1}, {"World": 2}]

    @abstractmethod
    def process_item(self, item):
        """Implement the analysis for each item of work here.

        :param item: One item of work from the queue (i.e., one item from the iterator that
                     was returned by the `setup` method).
        :type item: object
        :return: Status code, 0 for OK
        :rtype: int
        """
        return 0

    def finalize(self, had_errors):
        """Perform any cleanup actions after all items have been processed.
        Subclasses may choose not to implement this, in which case it is a no-op.

        :param had_errors: True if the run itself had errors.
        :type had_errors: bool
        :return: True if nothing went wrong, else False
        """
        return True

    # -----------------------------

    def run(self, setup_kw=None, build_kw=None):
        """Run the builder.

        :param setup_kw: keywords to pass to `setup()` method
        :type setup_kw: dict
        :param build_kw: keywords to pass to `_build()` method
        :type build_kw: dict
        :return: Number of items processed
        :rtype: int
        """
        setup_kw = {} if setup_kw is None else setup_kw
        build_kw = {} if build_kw is None else build_kw
        n = self._build(self.setup(**setup_kw), **build_kw)
        finalized = self.finalize(self._status.has_failures())
        if not finalized:
            _log.error("Finalization failed")
        return n

    def connect(self, config):
        """Connect to database with given configuration, which may be a dict or
        a path to a pymatgen-db configuration.
        """
        if isinstance(config, str):
            conn = dbutil.get_database(config_file=config)
        elif isinstance(config, dict):
            conn = dbutil.get_database(settings=config)
        else:
            raise ValueError("Configuration, '{}',  must be a path to config file or dict"
                             .format(config))
        return conn

    # -----------------------------

    def _build(self, items, chunk_size=1000):
        """Build the output, in chunks.

        :return: Number of items processed
        :rtype: int
        """
        n, i = 0, 0
        for i, item in enumerate(items):
            if 0 == (i+1) % chunk_size:
                self._run_parallel_fn()  # process the chunk
                if self._status.has_failures():
                    break
                n = i + 1
            self._queue.put(item)
        # process final chunk
        self._run_parallel_fn()
        if not self._status.has_failures():
            n = i + 1
        return n

    def _run_parallel_threaded(self):
        """Run threads from queue
        """
        _log.debug("run.parallel.threaded.start")
        threads = []
        for i in xrange(self._ncores):
            thr = threading.Thread(target=self._run, args=(i,))
            self._status.running(i)
            thr.start()
            threads.append(thr)
        for i in xrange(self._ncores):
            threads[i].join()
            if threads[i].isAlive():    # timed out
                _log.warn("run.parallel.threaded: timeout for thread={:d}".format(i))
        _log.debug("run.parallel.threaded.end states={}".format(self._status))

    def _run_parallel_multiprocess(self):
        """Run processes from queue
        """
        _log.debug("run.parallel.multiprocess.start")
        processes = []
        ProcRunner.instance = self
        for i in xrange(self._ncores):
            self._status.running(i)
            proc = multiprocessing.Process(target=ProcRunner.run, args=(i,))
            proc.start()
            processes.append(proc)
        for i in xrange(self._ncores):
            processes[i].join()
            code = processes[i].exitcode
            self._status.success(i) if 0 == code else self._status.fail(i)
        _log.debug("run.parallel.multiprocess.end states={}".format(self._status))

    def _run(self, index):
        """Run method for one thread or process
        Just pull an item off the queue and process it,
        until the queue is empty.

        :param index: Sequential index of this process or thread
        :type index: int
        """
        while 1:
            try:
                item = self._queue.get(timeout=2)
                self.process_item(item)
            except Queue.Empty:
                break
            except Exception, err:
                _log.error("Processing exception: {}".format(err))
                self._status.fail(index)
                raise
        self._status.success(index)

    def __str__(self):
        return self.__class__.__name__


class BuilderStatus(object):
    """Status of a Builder object run.
    """
    # States
    WAIT, RUNNING, SUCCESS, FAILURE = 0, 1, 2, -1
    # For printing.
    _NAMES = {WAIT: "wait", RUNNING: "run", SUCCESS: "ok", FAILURE: "fail"}

    def __init__(self, num, is_threaded=False):
        self._states = [self.WAIT] * num
        self._threaded = is_threaded
        if self._threaded:
            self._lock = threading.Lock()

    def running(self, i):
        """Set state of a single process or thread to 'running'.

        :param i: Index of process or thread.
        :return: None
        """
        self._set(i, self.RUNNING)

    def success(self, i):
        """Set state of a single process or thread to 'success'.

        :param i: Index of process or thread.
        :return: None
        """
        self._set(i, self.SUCCESS)

    def fail(self, i):
        """Set state of a single process or thread to 'failure'.

        :param i: Index of process or thread.
        :return: None
        """
        self._set(i, self.FAILURE)

    def has_failures(self):
        """Whether there are any failures in the states.
        """
        return self.FAILURE in self._states

    def _set(self, index, value):
        if self._threaded:
            self._lock.acquire()
        self._states[index] = value
        if self._threaded:
            self._lock.release()

    def __getitem__(self, index):
        if self._threaded:
            self._lock.acquire()
        value = self._states[index]
        if self._threaded:
            self._lock.release()
        return value

    def __str__(self):
        return ",".join([self._NAMES[state] for state in self._states])


class ProcRunner:
    """This is a work-around to the limitation of multiprocessing that the
    function executed in the new module cannot be a method of a class.
    We simply set the instance (self) into the class before forking each
    process, and the class' method calls the instance method for us.
    """
    instance = None

    @classmethod
    def run(cls, index):
        cls.instance._run(index)


def alphadump(d, indent=2, depth=0):
    """Dump a dict to a str,
    with keys in alphabetical order.
    """
    sep = '\n' + ' ' * depth * indent
    return ''.join(
        ("{}: {}{}".format(
            k,
            alphadump(d[k], depth=depth+1) if isinstance(d[k], dict)
            else str(d[k]),
            sep)
         for k in sorted(d.keys()))
    )
