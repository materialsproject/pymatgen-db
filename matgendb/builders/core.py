"""
Shared code for builders.

For developers implementing a new builder,
you should inherit from `ParallelBuilder`. See the
documentation of this class for details.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '5/29/13'

## Imports

import copy
import logging
import Queue
import threading
import multiprocessing

from pymatpro.db import schema

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

    This is a way to get some `static` checking of the schema of inserted documents,
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
    def run(self):
        """This method should:
        (1) put work in the queue with add_item()
        (2) call run_parallel() to do the work

        :return: Status code, 0 for OK
        :rtype: int
        """
        raise NotImplementedError()

    def add_item(self, item):
        """Add an item of work to be performed.
        """
        raise NotImplementedError()

    def process_item(self, item):
        """Implement the analysis for each item of work here.

        :param item: One item of work from the queue
        :type item: object
        :return: Status code, 0 for OK
        :rtype: int
        """
        raise NotImplementedError()

    def combine_status(self, codes):
        """Combine integer status codes.

        :return: -1 if any is nonzero, else 0
        """
        return (-1, 0)[not filter(None, codes)]

    def __str__(self):
        return self.__class__.__name__


class ParallelBuilder(Builder, HasExamples):
    """Parallel builder base class.
        All the builder classes should inherit from this.

    Subclasses should define two methods:

    `run` - Do any serial tasks, then put all objects that must 
    be operated on in parallel into the queue, one at a time,
    by calling `add_item`. Then call `run_parallel`. The return value of this function
    is a list of status codes, one per thread/process. 
    You can join the status codes with `combine_status`.

    process_item(item) - Do the work for one item. Return integer status
            code, 0 for OK and non-zero for failure.
    """
    def __init__(self, ncores=0, threads=False, combine_status=False):
        """Create new builder for threaded or multiprocess execution.

        :param ncores: Desired number of threads/processes to run
        :type ncores: int
        :param threads: Use threads (True) or processes (False)
        :type threads: bool
        :param combine_status: Flag to combine status codes into 1 code
        :type combine_status: bool
        """
        self._ncores = ncores if ncores else 15
        self._threaded = threads
        if threads:
            self._queue = Queue.Queue()
            self._states_lock = threading.Lock()
            self._run_parallel_mode = self._run_parallel_threaded
        else:
            self._queue = multiprocessing.Queue()
            self._run_parallel_mode = self._run_parallel_multiprocess
        self._states = []
        self._combine = combine_status

    def add_item(self, item):
        """Put an item of work in the queue.
        Subclasses do not need to modify this.
        """
        self._queue.put(item)

    def run_parallel(self):
        """Called to run threads, once queue is filled.

        :return: Multiple integer status codes, 1 per thread
        :rtype: list(int)
        """
        result = self._run_parallel_mode()
        if self._combine:
            result = self.combine_status(result)
        return result

    def _run_parallel_threaded(self):
        """Called to run threads, once queue is filled.

        :return: array of integer status codes, 1 per thread
        """
        _log.debug("run.parallel.threaded.start")
        threads = []
        for i in xrange(self._ncores):
            thr = threading.Thread(target=self._run)
            thr.start()
            threads.append(thr)
        for i in xrange(self._ncores):
            threads[i].join()
            if threads[i].isAlive():    # timed out
                _log.warn("run.parallel.threaded: timeout for thread={:d}".format(i))
        _log.debug("run.parallel.threaded.end states={}".format(self._set_status()))
        return self._set_status()

    def _run_parallel_multiprocess(self):
        """Called to run processes, once queue is filled.

        :return: array of integer status codes, 1 per thread
        """
        _log.debug("run.parallel.multiprocess.start")
        processes = []
        ProcRunner.instance = self
        for i in xrange(self._ncores):
            proc = multiprocessing.Process(target=ProcRunner.run)
            proc.start()
            processes.append(proc)
        states = []
        for i in xrange(self._ncores):
            processes[i].join()
            states.append(processes[i].exitcode)
        _log.debug("run.parallel.multiprocess.end states={}".format(','.join(map(str, states))))
        return states

    def _run(self):
        """Run method for one thread or process
        Just pull an item off the queue and process it,
        until the queue is empty.
        """
        while 1:
            try:
                item = self._queue.get(timeout=2)
                self.process_item(item)
            except Queue.Empty:
                break
            except Exception, err:
                _log.error("Processing exception: {}".format(err))
                self._set_status(-1)
                raise
        self._set_status(0)

    def _set_status(self, value=None):
        if self._threaded:
            self._states_lock.acquire()
            if value is not None:
                self._states.append(value)
            result = self._states[:]
            self._states_lock.release()
            return result
        else:
            return value


class ProcRunner:
    """This is a work-around to the limitation of multiprocessing that the
    function executed in the new module cannot be a method of a class.
    We simply set the instance (self) into the class before forking each
    process, and the class' method calls the instance method for us.
    """
    instance = None

    @classmethod
    def run(cls):
        cls.instance._run()



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
