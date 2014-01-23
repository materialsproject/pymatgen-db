"""
Diff collections, as sets
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '3/29/13'

import logging
import time
from matgendb import util

_log = logging.getLogger("mg.vv.diff")


class Differ(object):
    """Calculate difference between two collections, based solely on a
    selected key.

    As noted in :func:`diff`, this will not work with huge datasets, as it stores
    all the keys in memory in order to do a "set difference" using Python sets.
    """

    # Whether to get extra display-only fields with initial query, 'early',
    # or after figuring out which fields are different.
    get_fields_early = False

    # Keys in result dictionary.
    MISSING, NEW = 'missing', 'additional'

    def __init__(self, key='_id', info=None, fltr=None):
        """Constructor.

        :param key: Field to use for identifying/matching records
        :param info: List of extra fields to retrieve from (and show) for each record.
        :param fltr: Filter for records, a MongoDB query expression
        """
        self._key = key
        self._info = [] if info is None else info
        self._filter = fltr if fltr else {}

    def diff(self, c1, c2, only_missing=False):
        """Perform a difference between the 2 collections.
        The first collection is treated as the previous one, and the second
        is treated as the new one.

        Note: this is not 'big data'-ready; we assume all the records can fit in memory.

        :param c1: Collection (1) config file
        :param c2: Collection (2) config file
        :param only_missing: Only find and return self.MISSING; ignore 'new' keys
        :return: dict with keys self.MISSING, self.NEW (unless only_missing is True),
                 each a list of records with the key and
                 any other fields given to the constructor 'info' argument.
                 The meaning is: 'missing' are keys that are in c1 not found in c2
                 'new' is keys found in c2 that are not found in c1.
        """
        # Connect.
        _log.info("connect.start")
        collections = map(util.get_collection, (c1, c2))
        _log.info("connect.end")

        # Query DB.
        keys = [set(), set()]
        fields = dict.fromkeys(self._info + [self._key], True)
        if not '_id' in fields:  # explicitly remove _id if not given
            fields['_id'] = False
        # approach (1): get all fields in initial query
        _log.debug("Get fields early = {}".format(self.get_fields_early))
        if self.get_fields_early:
            save_fields = None
        # approach (2): get only key, query for deltas
        else:
            save_fields, fields = fields, {self._key: True}
        data, has_info = {}, bool(self._info)
        _log.info("query.start")
        t0 = time.time()
        for i, coll in enumerate(collections):
            _log.debug("collection {:d}".format(i))
            for rec in coll.find(self._filter, fields=fields):
                key = rec[self._key]
                # TODO: Add some handling of duplicate keys?
                # TODO: Current method silently uses last one seen.
                try:
                    keys[i].add(key)
                except KeyError:
                    _log.critical("Key '{}' not found in record: {}. Abort.".format(
                                  self._key, rec))
                    return {}
                if has_info and self.get_fields_early:
                    data[key] = rec
        t1 = time.time()
        _log.info("query.end sec={:f}".format(t1 - t0))
        _log.debug("compute_difference.start")
        missing = keys[0] - keys[1]
        if not only_missing:
            new = keys[1] - keys[0]
        _log.debug("compute_difference.end")

        # Build result.
        _log.debug("build_result.begin")
        result = {self.MISSING: []}
        if not only_missing:
            result[self.NEW] = []
        if has_info:
            # approach (1): got all fields in initial query
            if self.get_fields_early:
                result[self.MISSING] = [data[key] for key in missing]
                if not only_missing:
                    result[self.NEW] = [data[key] for key in new]
            # approach (2): need to pull full info now.
            else:
                fields, batch_size = save_fields, 50
                if only_missing:
                    fetchlist = ((0, self.MISSING, missing),)
                else:
                    fetchlist = ((0, self.MISSING, missing), (1, self.NEW, new))
                for i, name, var_ in fetchlist:
                    keys = list(var_)
                    for batch_start in xrange(0, len(keys), batch_size):
                        fetch_keys = keys[batch_start:batch_start + batch_size]
                        coll = collections[i]
                        records = list(coll.find({self._key: {'$in': fetch_keys}}, fields=fields))
                        result[name].extend(records)
        else:
            result[self.MISSING] = [{self._key: key} for key in missing]
            if not only_missing:
                result[self.NEW] = [{self._key: key} for key in new]
        _log.debug("build_result.end")

        return result
