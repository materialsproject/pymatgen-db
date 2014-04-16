"""
Incremental builders.

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


class DBError(Exception):
    """Generic database error.
    """
    pass


class Operation(Enum):
    """Enumeration of collection operations.
    """
    copy = 1
    build = 2
    other = 3


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

    def __init__(self, coll):
        """Constructor.

       :param coll: Collection to track
       :type coll: pymongo.collection.Collection
        """
        self.collection, self.db = coll, coll.database
        self._track = self.db[self.tracking_collection_name]

    @property
    def tracking_collection_name(self):
        return self.collection.name + '.' + self.TRACKING_NAME

    @property
    def tracking_collection(self):
        return self._track

    def save(self, mark):
        """Save a position in this collection.

        :param mark: The position to save
        :type mark: Mark
        :raises: DBError
        """
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
        """
        query = {Mark.FLD_OP: operation.name,
                 Mark.FLD_MARK + "." + field: {"$exists": True}}
        obj = self._track.find_one(query)
        if obj is None:
            # empty Mark instance
            return Mark(collection=self.collection, operation=operation)
        return Mark.from_dict(obj)




