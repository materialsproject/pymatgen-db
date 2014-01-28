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

    #: Keys in result dictionary.
    MISSING, NEW, CHANGED = 'missing', 'additional', 'different'

    #: for missing property
    NO_PROPERTY = "__MISSING__"

    def __init__(self, key='_id', props=None, info=None, fltr=None):
        """Constructor.

        :param key: Field to use for identifying records
        :param props: List of fields to use for matching records
        :param info: List of extra fields to retrieve from (and show) for each record.
        :param fltr: Filter for records, a MongoDB query expression
        """
        self._key = key
        self._props = [] if props is None else props
        self._info = [] if info is None else info
        self._filter = fltr if fltr else {}

    def diff(self, c1, c2, only_missing=False, allow_dup=False):
        """Perform a difference between the 2 collections.
        The first collection is treated as the previous one, and the second
        is treated as the new one.

        Note: this is not 'big data'-ready; we assume all the records can fit in memory.

        :param c1: Collection (1) config file
        :param c2: Collection (2) config file
        :param only_missing: Only find and return self.MISSING; ignore 'new' keys
        :param allow_dup: Allow duplicate keys, otherwise fail with ValueError
        :return: dict with keys self.MISSING, self.NEW (unless only_missing is True), & self.CHANGED,
                 each a list of records with the key and
                 any other fields given to the constructor 'info' argument.
                 The meaning is: 'missing' are keys that are in c1 not found in c2
                 'new' is keys found in c2 that are not found in c1, and 'changed' are records
                 with the same key that have different 'props' values.
        """
        # Connect.
        _log.info("connect.start")
        collections = map(util.get_collection, (c1, c2))
        _log.info("connect.end")

        # Query DB.
        keys = [set(), set()]
        props = [{}, {}]
        fields = dict.fromkeys(self._info + self._props + [self._key], True)
        if not '_id' in fields:  # explicitly remove _id if not given
            fields['_id'] = False
        data, has_info, has_props = {}, bool(self._info), bool(self._props)
        _log.info("query.start")
        t0 = time.time()
        for i, coll in enumerate(collections):
            _log.debug("collection {:d}".format(i))
            count, missing_props = 0, 0
            for rec in coll.find(self._filter, fields=fields):
                count += 1
                key = rec[self._key]
                if not allow_dup and key in keys[i]:
                    raise ValueError("Duplicate key: {}".format(key))
                try:
                    keys[i].add(key)
                except KeyError:
                    _log.critical("Key '{}' not found in record: {}. Abort.".format(
                                  self._key, rec))
                    return {}
                if has_props:
                    # Extract properties, and index by key.
                    try:
                        propval = tuple([(p, str(rec[p])) for p in self._props])
                    except KeyError:
                        missing_props += 1
                        continue
                    props[i][key] = propval
                if i == 0 and has_info:
                    data[key] = rec
            if missing_props == count:
                _log.critical("Missing one or more properties on all {:d} records"
                        .format(count))
                return {}
            elif missing_props > 0:
                _log.warn("Missing one or more properties for {:d}/{:d} records"
                        .format(missing_props, count))
        t1 = time.time()
        _log.info("query.end sec={:f}".format(t1 - t0))

        # Compute missing and new keys.
        _log.debug("compute_difference.start")
        missing = keys[0] - keys[1]
        if not only_missing:
            new = keys[1] - keys[0]
        _log.debug("compute_difference.end")

        # Compute mis-matched properties.
        changed = []
        if has_props:
            for key in keys[0].intersection(keys[1]):
                if props[0][key] != props[1][key]:
                    crec = {self._key: key, 'old': props[0][key], 'new': props[1][key]}
                    if has_info:
                        drec = data[key]
                        crec.update({k: drec[k] for k in self._info})
                    changed.append(crec)

        # Build result.
        _log.debug("build_result.begin")
        result = {self.MISSING: []}
        if not only_missing:
            result[self.NEW] = []
        if has_info:
            result[self.MISSING] = [data[key] for key in missing]
            if not only_missing:
                result[self.NEW] = [data[key] for key in new]
        else:
            result[self.MISSING] = [{self._key: key} for key in missing]
            if not only_missing:
                result[self.NEW] = [{self._key: key} for key in new]
        result[self.CHANGED] = changed
        _log.debug("build_result.end")

        return result
