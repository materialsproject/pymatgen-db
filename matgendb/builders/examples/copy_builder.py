"""
Simple "copy" builder.

Copies from one collection to another.
With the optional incremental feature, running twice will only copy the new records, i.e.
running twice in succession will cause the second run to do nothing.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/22/14'


from matgendb.builders import core as bld_core
from matgendb.query_engine import QueryEngine

class TaskBuilder(bld_core.Builder):
    def setup(self, source, target, crit):
        """Copy records from source to target collection.

        :param source: Input collection
        :type source: QueryEngine
        :param target: Output collection
        :type target: QueryEngine
        :param crit: Optional filter criteria
        :type qcrit dict
        """
        self._target_coll = target.collection
        if not crit:  # reduce any False-y crit value to an empty dict
            crit = dict()
        return source.query(criteria=crit)

    def process_item(self, item):
        self._target_coll.insert(item)
