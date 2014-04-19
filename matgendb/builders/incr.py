"""
Incremental builders.

## High-level API ##

The main class is TrackedQueryEngine. Usage example::

    from matgendb.builders.incr import *
    qe = TrackedQueryEngine(track_operation=Operation.copy,
                            track_field='_id', ...other kw...)
    # That's it! Use as you normally would.
    # The collection 'inside' the qe will be tracked, so
    # when you are done using the QE instance, you can call either
    qe.set_mark()
    # or
    qe.collection.set_mark()
    # Just be sure not to set the collection attribute directly,
    # always use qe.set_collection("new_name")

## Low-level API ##

The main classes are Mark and CollectionTracker. Usage example::

    from matgendb.builders.incr import *
    collection = pymongo.MongoClient().mydb.mycollection
    # Init tracker
    tracker = CollectionTracker(collection)
    # Save mark for copy operation
    tracker.save(Mark(collection, Operation.copy, field='_id'))
    # Retrieve mark for copy operation
    mark = tracker.retrieve(Operation.copy, field='_id')
    # Update mark position, and print mark
    print(mark.update().as_dict())

"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/11/14'

import pymongo
from enum import Enum
from matgendb.query_engine import QueryEngine


class DBError(Exception):
    """Generic database error.
    """
    pass


class NoTrackingCollection(Exception):
    """Raised if no tracking collection is present,
    but some operation is requested on that collection.
    """
    pass


## --------------
## High level API
## --------------

class TrackedQueryEngine(QueryEngine):
    """A QE that only examines records past the last 'mark' that was set for the
    given operation and field.
    """
    def __init__(self, track_operation=None, track_field=None, **kwargs):
        QueryEngine.__init__(self, **kwargs)
        self._t_op, self._t_field = track_operation, track_field  # shotput!

    def set_collection(self, coll_name):
        """Override base class to make this a tracked collection.
        """
        coll = self.db[coll_name]
        return TrackedCollection(coll, operation=self._t_op, field=self._t_field)

    def set_mark(self):
        """Set the mark to the current end of the collection. This is saved in the database
        so it is available for later operations.
        """
        self.collection.set_mark()


class TrackedCollection(object):
    def __init__(self, coll, operation=None, field=None):
        self._coll, self._coll_find = coll, coll.find
        self._tracker = CollectionTracker(coll, create=True)
        self._mark = self._tracker.retrieve(operation=operation, field=field)

    def __getattr__(self, item):
        if item == 'find':
            # monkey-patch the find() method in the collection object
            return self.tracked_find
        else:
            return getattr(self._coll, item)

    def tracked_find(self, *args, **kwargs):
        # fish 'spec' out of args or kwargs
        if len(args) > 0:
            spec = args[0]
        else:
            if 'spec' not in kwargs:
                kwargs['spec'] = {}
            spec = kwargs['spec']
        # update spec with tracker query
        spec.update(self._mark.query)
        # delegate to "real" find()
        return self._coll_find(*args, **kwargs)

    def set_mark(self):
        self._tracker.save(self._mark.update())


## --------------
## Low level API
## --------------

class Operation(Enum):
    """Enumeration of collection operations.
    """
    copy = 1
    build = 2
    other = 99


class Mark(object):
    """The position in a collection for the last record that was
    processed by a given operation.
    """
    # Fields for JSON representation
    FLD_OP, FLD_MARK = "operation", "mark"

    def __init__(self, collection=None, operation=None, field=None, kvp=None):
        """Constructor.

        Can be called in two ways, with `kvp` set to a dict describing the
        highest record values, or with `field` giving the field in the collection
        to use for finding the highest values. If both are provided,
        the `kvp` takes precedence, but will be replaced with a call to :meth:`update`.
        If neither is provided, the Mark has an "empty" position of {<field>: 0}.

        :param collection: Collection to track
        :type collection: pymongo.collection.Collection
        :param operation: Operation for this mark.
        :type operation: Operation
        :param field: Name of field to determine highest record
        :type field: str
        :param kvp: Key/value pairs that describe the mark position
        :type kvp: dict
        """
        self._c = collection
        self._op = operation
        self._fld = field
        if kvp:
            self._pos = kvp
        elif field:
            self.update()
        else:
            self._pos = self._empty_pos()

    def update(self):
        """Update the position of the mark in the collection.

        :return: this object, for chaining
        :rtype: Mark
        """
        rec = self._c.find_one({}, {self._fld: 1}, sort=[(self._fld, -1)], limit=1)
        self._pos = self._empty_pos() if rec is None else rec
        return self

    def _empty_pos(self):
        return {self._fld: 0}

    @property
    def pos(self):
        return self._pos

    def as_dict(self):
        """Representation as a dict for JSON serialization.
        """
        return {self.FLD_OP: self._op.name,
                self.FLD_MARK: self._pos}

    to_dict = as_dict   # synonym

    @classmethod
    def from_dict(cls, d):
        """Construct from dict

        :param d: Input
        :type d: dict
        :return: new instance
        :rtype: Mark
        """
        return Mark(operation=Operation[d[cls.FLD_OP]], kvp=d[cls.FLD_MARK])

    @property
    def query(self):
        """A mongdb query expression to find all records with higher values
        for this mark's fields in the collection.

        :rtype: dict
        """
        return {key: {'$gt': val} for key, val in self._pos.iteritems()}


class CollectionTracker(object):
    """Track which records are 'new' in a MongoDB collection
    with respect to a given operation.
    """
    #: Sub-collection name, added as ".TRACKING_NAME" to the
    #: name of the target collection to create the tracking collection.
    TRACKING_NAME = 'tracker'

    def __init__(self, coll, create=True):
        """Constructor.

        :param coll: Collection to track
        :type coll: pymongo.collection.Collection
        :param create: Create tracking collection, if not present. Otherwise the tracking
                       collection can be manually created with :meth:`create`, later.
                       If the collection is not created, :meth:`save` and :meth:`retrieve` will
                       raise a `NoTrackingCollection` exception.
        :type create: bool
        """
        self.collection, self.db = coll, coll.database
        trk = self.tracking_collection_name
        if not create and trk not in self.db.collection_names(False):
            self._track = None
        else:
            self._track = self.db[trk]

    @property
    def tracking_collection_name(self):
        return self.collection.name + '.' + self.TRACKING_NAME

    @property
    def tracking_collection(self):
        """Return current tracking collection, or None if it does not exist.
        """
        return self._track

    def create(self):
        """Create tracking collection.
        Does nothing if tracking collection already exists.
        """
        if self._track is None:
            self._track = self.db[self.tracking_collection_name]

    def save(self, mark):
        """Save a position in this collection.

        :param mark: The position to save
        :type mark: Mark
        :raises: DBError, NoTrackingCollection
        """
        self._check_exists()
        obj = mark.as_dict()
        try:
            self._track.insert(obj)
        except pymongo.errors.PyMongoError, err:
            raise DBError("{}".format(err))

    def retrieve(self, operation, field=None):
        """Retrieve a position in this collection.

        :param operation: Name of an operation
        :type operation: :class:`Operation`
        :param field: Name of field for sort order
        :type field: str
        :return: The position for this operation
        :rtype: Mark
        :raises: NoTrackingCollection
        """
        obj = self._get(operation, field)
        if obj is None:
            # empty Mark instance
            return Mark(collection=self.collection, operation=operation)
        return Mark.from_dict(obj)

    def _get(self, operation, field):
        self._check_exists()
        query = {Mark.FLD_OP: operation.name,
                 Mark.FLD_MARK + "." + field: {"$exists": True}}
        return self._track.find_one(query)

    def _check_exists(self):
        if self._track is None:
            raise NoTrackingCollection()