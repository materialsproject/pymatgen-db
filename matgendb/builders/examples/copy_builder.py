"""
Simple "copy" builder.

Copies from one collection to another.
With the optional incremental feature, running twice will only copy the new records, i.e.
running twice in succession will cause the second run to do nothing.

To run:

mgbuild
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/22/14'


from matgendb.builders import core as bld_core
from matgendb.query_engine import QueryEngine

_log = bld_core.get_builder_log("copy")


class Builder(bld_core.Builder):
    def __init__(self, *args, **kwargs):
        self._target_coll = None
        bld_core.Builder.__init__(self, *args, **kwargs)

    def setup(self, source=None, target=None, crit=None):
        """Copy records from source to target collection.

        :param source: Input collection
        :type source: QueryEngine
        :param target: Output collection
        :type target: QueryEngine
        :param crit: Filter criteria, e.g. "{ 'flag': True }. (optional)"
        :type crit: dict
        """
        self._target_coll = target.collection
        if not crit:  # reduce any False-y crit value to None
            crit = None
        _log.info("query, crit={} source={} target.coll={}".format(crit, source, target.collection))
        return source.query(criteria=crit)

    def process_item(self, item):
        assert self._target_coll
        _log.debug("insert item")
        self._target_coll.insert(item)
