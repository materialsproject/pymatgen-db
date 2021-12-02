"""
Simple "copy" builder.

Copies from one collection to another.
With the optional incremental feature, running twice will only copy the new records, i.e.
running twice in succession will cause the second run to do nothing.

To run:

mgbuild
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "4/22/14"

from pymatgen.db.builders import core
from pymatgen.db.builders import util
from pymatgen.db.query_engine import QueryEngine

_log = util.get_builder_log("copy")


class CopyBuilder(core.Builder):
    """Copy from one MongoDB collection to another."""

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
        _log.info(f"source.collection={source.collection} crit={crit} source_records={len(cur):d}")
        return cur

    def process_item(self, item):
        assert self._target_coll
        self._target_coll.insert_one(item)
