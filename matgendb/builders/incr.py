"""
Incremental builders
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


class CollectionExtractor(object):
    """Extract highest identifier from a collection.
    """
    def __init__(self, coll):
        self.coll = coll

    def highest(self):
        """Return key / value pair for highest id.

        For example::

            {'myid': 12345}

        :return: Simple key/value pair for highest id, empty for an empty collection.
        :rtype: dict
        """
        try:
            return self._highest()
        except IndexError:
            return {}

    def _highest(self):
        """Override in subclasses to return key/value pair for highest id.
        Raise IndexError if the collection is empty (i.e. simply use cursor[0]).
        """
        pass


class IdExtractor(CollectionExtractor):
    """Extract highest `_id`
    """
    def _highest(self):
        cursor = self.coll.find({}, {"_id": 1}, sort=[("_id", -1)], limit=1)
        return cursor[0]


class CollectionTracker(object):
    """Track which records are 'new' in a MongoDB collection
    with respect to a given operation.
    """
    #: Sub-collection name, added as ".TRACKING_NAME" to the
    #: name of the target collection to create the tracking collection.
    TRACKING_NAME = 'tracker'

    # Fields in tracking collection
    FLD_OP, FLD_MARK = "operation", "mark"

    def __init__(self, coll, extractor):
        """Constructor.

       :param coll: Collection to track
       :type coll: pymongo.collection.Collection
       :param extractor: Class to use for extracting the highest identifier.
       :type extractor: :class:`CollectionIdExtractor`
        """
        self.collection, self.db = coll, coll.database
        self._track = self.db[self.TRACKING_NAME]
        self._extract = extractor(coll)

    def set_mark(self, operation):
        """Set a mark for the given operation.

        :param operation: Name of an operation
        :type operation: :class:`Operation`
        :raises: DBError
        """
        try:
            self._set_mark(operation)
        except pymongo.errors.PyMongoError, err:
            raise DBError("{}".format(err))

    def _set_mark(self, operation):
        highest = self._extract.highest()
        expr = {key: {'$gt': val} for key, val in highest.iteritems()}
        obj = {self.FLD_OP: operation.name,
               self.FLD_MARK: expr}
        self._track.insert(obj)

    def get_mark(self, operation):
        """Get a query expression that will find records
        after the point last set by :meth:`set_mark`, for the given operation.

        The returned expression will be a dict like this:

            {"field": { "$gt" : value }, ... }

        :param operation: Name of an operation
        :type operation: :class:`Operation`
        :return: Mongo query expression. An empty expression if there is no mark,
                 or the mark was set in an empty collection.
        :rtype: dict
        """
        obj = self._track.find_one({self.FLD_OP: operation.name})
        return obj[self.FLD_MARK]

    def find(self, operation, query=None, **kwargs):
        """Perform a query on the original collection that will return
        only records after the point last set by :meth:`set_mark`, for the given operation.

        This is a convenience function, as `tracker.find(oper, query)` is equivalent to
        `query.update(tracker.get_mark(oper)); tracker.collection.find(query)`.

        :param operation: Name of an operation
        :type operation: :class:`Operation`
        :param query: Additional query expression to include in query
        :type query: dict or None
        :param kwargs: Additional keywords passed to `pymongo.collection.Collection.find()`
        :return: Cursor over results
        :rtype: pymongo.cursor.Cursor
        """
        pass


