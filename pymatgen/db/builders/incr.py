"""
Incremental builders.

## High-level API ##

The main class is TrackedQueryEngine. Usage example::

    from pymatgen.db.builders.incr import *
    qe = TrackedQueryEngine(track_operation=Operation.copy,
                            track_field='_id', ...other kw...)
    # That's it! Use as you normally would.
    # The collection 'inside' the qe will be tracked, so
    # when you are done using the QE instance, you can call either
    qe.set_mark()
    # or
    qe.collection.set_mark()
    # Just be sure not to set the `qe.collection` attribute directly,
    # always use `qe.collection_name = "new_name" (which calls a setter)`.

## Low-level API ##

The main classes are Mark and CollectionTracker. Usage example::

    from pymatgen.db.builders.incr import *
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
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "4/11/14"

from abc import abstractmethod, ABCMeta
import pymongo
from enum import Enum
from pymatgen.db.query_engine import QueryEngine
from pymatgen.db.builders import util as bld_util

# Logging

_log = bld_util.get_builder_log("incr")

# Exceptions


class DBError(Exception):
    """Generic database error."""

    pass


class NoTrackingCollection(Exception):
    """Raised if no tracking collection is present,
    but some operation is requested on that collection.
    """

    pass


## --------------
## High level API
## --------------


class TrackingInterface(metaclass=ABCMeta):
    @abstractmethod
    def set_mark(self):
        """Set the mark to the current end of the collection. This is saved in the database
        so it is available for later operations.
        """
        pass


class UnTrackedQueryEngine(QueryEngine, TrackingInterface):
    """A QE that has the interface for tracking, but does nothing for it.
    Allows for callers to do same operations regardless of whether tracking is
    activated or not.
    """

    def set_mark(self):
        """Does nothing and returns None."""
        return


class TrackedQueryEngine(QueryEngine, TrackingInterface):
    """A QueryEngine subclass that only examines records
    past the last 'mark' that was set for the
    given operation and field.

    The concrete result is that for an object, ``t``, the
    ``t.find()`` method will start *past* the "mark".

    To go around this transparent change, use the ``t.findall``
    instead.
    """

    def __init__(self, track_operation=None, track_field=None, **kwargs):
        """Constructor."""
        self._tracking_off = False
        # Set these first because QueryEngine.__init__ calls overridden `collection_name setter()`.
        assert track_field
        self._t_op, self._t_field = track_operation, track_field
        self.collection = None
        # Now init parent
        QueryEngine.__init__(self, **kwargs)

    @property
    def tracking(self):
        """Whether tracking is really enabled."""
        return not self._tracking_off

    @tracking.setter
    def tracking(self, is_tracked):
        self._tracking_off = not is_tracked
        if self.collection is not None:
            self.collection.set_tracking(is_tracked)

    @property
    def collection_name(self):
        """Override base class to make this a tracked collection.
        See :meth:`@collection_name.setter`
        """
        return self._collection_name

    @collection_name.setter
    def collection_name(self, value):
        """Switch to another collection.
        Note that you may have to set the aliases and default properties if the
        schema of the new collection differs from the current collection.
        """
        self._collection_name = value
        self._mongo_coll = self.db[value]
        self.collection = TrackedCollection(self._mongo_coll, operation=self._t_op, field=self._t_field)

    def set_mark(self):
        """See :meth:`TrackingInterface.set_mark`"""
        assert self.collection
        self.collection.set_mark()


class TrackedCollection:
    """Wrapper on a pymongo collection to make `find' operations start
    after the "tracking" mark.
    """

    def __init__(self, coll, operation=None, field=None):
        self._coll, self._coll_find = coll, coll.find
        self._tracking_off = False
        self._tracker = CollectionTracker(coll, create=True)
        self._mark = self._tracker.retrieve(operation=operation, field=field)

    def set_tracking(self, is_tracked):
        """Set whether find() transparently starts from after the
        mark (True), or whether it ignores the tracking info and acts like
        a normal ``find()`` operation (False).

        :param is_tracked: Whether to use tracking info
        :return:
        """
        self._tracking_off = not is_tracked

    def findall(self, *args, **kwargs):
        """Call non-tracked ``find()`` operation with same args."""
        return self._coll.find(*args, **kwargs)

    def __getattr__(self, item):
        if item == "find":
            # monkey-patch the find() method in the collection object
            return self.tracked_find
        else:
            return getattr(self._coll, item)

    def __str__(self):
        return f"Tracked collection ({self._coll})"

    def tracked_find(self, *args, **kwargs):
        """Replacement for regular ``find()``."""
        _log.info("tracked_find.begin")
        # if tracking is off, just call find (ie do nothing)
        if self._tracking_off:
            _log.info("tracked_find.end, tracking=off")
            return self._coll_find(*args, **kwargs)
        # otherwise do somethin' real
        # fish 'filter' out of args or kwargs
        if len(args) > 0:
            filt = args[0]
        else:
            if "filter" not in kwargs:
                kwargs["filter"] = {}
            filt = kwargs["filter"]
        # update filter with tracker query
        filt.update(self._mark.query)
        # delegate to "real" find()
        _log.info(f"tracked_find.end, call: {self._coll.name}.find(args={args} kwargs={kwargs})")
        return self._coll_find(*args, **kwargs)

    def set_mark(self):
        self._tracker.save(self._mark.update())


# TODO: TrackedFileset -- Same basic idea with one or more files in a directory.
# TODO: This would enable the incremental interface to work just as well with loading
# TODO: from files into the DB as it does with DB -> DB operations.


## --------------
## Low level API
## --------------


class Operation(Enum):
    """Enumeration of collection operations."""

    copy = 1
    build = 2
    other = 99


class Mark:
    """The position in a collection for the last record that was
    processed by a given operation.
    """

    # Fields for JSON representation
    FLD_OP, FLD_MARK, FLD_FLD = "operation", "mark", "field"

    def __init__(self, collection=None, operation=None, field=None, pos=None):
        """Constructor.

        :param collection: Collection to track
        :type collection: pymongo.collection.Collection
        :param operation: Operation for this mark.
        :type operation: Operation
        :param field: Name of field to determine highest record
        :type field: str
        :param pos: Optional query for position
        :type pos: dict
        """
        self._c = collection
        self._op = operation
        self._fld = field
        assert self._fld
        if pos:
            self._pos = pos
        else:
            self._pos = self._empty_pos()

    def update(self):
        """Update the position of the mark in the collection.

        :return: this object, for chaining
        :rtype: Mark
        """
        rec = self._c.find_one({}, {self._fld: 1}, sort=[(self._fld, -1)], limit=1)
        if rec is None:
            self._pos = self._empty_pos()
        elif not self._fld in rec:
            _log.error(f"Tracking field not found. field={self._fld} collection={self._c.name}")
            _log.warn("Continuing without tracking")
            self._pos = self._empty_pos()
        else:
            self._pos = {self._fld: rec[self._fld]}
        return self

    def _empty_pos(self):
        return {self._fld: None}

    @property
    def pos(self):
        return self._pos

    def as_dict(self):
        """Representation as a dict for JSON serialization."""
        return {
            self.FLD_OP: self._op.name,
            self.FLD_MARK: self._pos,
            self.FLD_FLD: self._fld,
        }

    to_dict = as_dict  # synonym

    @classmethod
    def from_dict(cls, coll, d):
        """Construct from dict

        :param coll: Collection for the mark
        :param d: Input
        :type d: dict
        :return: new instance
        :rtype: Mark
        """
        return Mark(
            collection=coll,
            operation=Operation[d[cls.FLD_OP]],
            pos=d[cls.FLD_MARK],
            field=d[cls.FLD_FLD],
        )

    @property
    def query(self):
        """A mongdb query expression to find all records with higher values
        for this mark's fields in the collection.

        :rtype: dict
        """
        q = {}
        for field, value in self._pos.items():
            if value is None:
                q.update({field: {"$exists": True}})
            else:
                q.update({field: {"$gt": value}})
        return q


class CollectionTracker:
    """Track which records are 'new' in a MongoDB collection
    with respect to a given operation.
    """

    #: Sub-collection name, added as ".<TRACKING_NAME>" to the
    #: name of the target collection to create the tracking collection.
    TRACKING_NAME = "tracker"

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
        return self.collection.name + "." + self.TRACKING_NAME

    @property
    def tracking_collection(self):
        """Return current tracking collection, or None if it does not exist."""
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
            # Make a 'filter' to find/update existing record, which uses
            # the field name and operation (but not the position).
            filt = {k: obj[k] for k in (mark.FLD_FLD, mark.FLD_OP)}
            _log.debug(f"save: upsert-spec={filt} upsert-obj={obj}")
            self._track.update(filt, obj, upsert=True)
        except pymongo.errors.PyMongoError as err:
            raise DBError(f"{err}")

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
            return Mark(collection=self.collection, operation=operation, field=field)
        return Mark.from_dict(self.collection, obj)

    def _get(self, operation, field):
        """Get tracked position for a given operation and field."""
        self._check_exists()
        query = {
            Mark.FLD_OP: operation.name,
            Mark.FLD_MARK + "." + field: {"$exists": True},
        }
        return self._track.find_one(query)

    def _check_exists(self):
        """Check whether the tracked collection exists at all.
        If not, raises NoTrackingCollection
        """
        if self._track is None:
            raise NoTrackingCollection()
