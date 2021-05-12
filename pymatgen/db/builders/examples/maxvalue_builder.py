"""
Build a derived collection with the maximum
value from each 'group' defined in the source
collection.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "5/21/14"

from pymatgen.db.builders import core
from pymatgen.db.builders import util
from pymatgen.db.query_engine import QueryEngine

_log = util.get_builder_log("incr")


class MaxValueBuilder(core.Builder):
    """Example of incremental builder that requires
    some custom logic for incremental case.
    """

    def get_items(self, source=None, target=None):
        """Get all records from source collection to add to target.

        :param source: Input collection
        :type source: QueryEngine
        :param target: Output collection
        :type target: QueryEngine
        """
        self._groups = self.shared_dict()
        self._target_coll = target.collection
        self._src = source
        return source.query()

    def process_item(self, item):
        """Calculate new maximum value for each group,
        for "new" items only.
        """
        group, value = item["group"], item["value"]
        if group in self._groups:
            cur_val = self._groups[group]
            self._groups[group] = max(cur_val, value)
        else:
            # New group. Could fetch old max. from target collection,
            # but for the sake of illustration recalculate it from
            # the source collection.
            self._src.tracking = False  # examine entire collection
            new_max = value
            for rec in self._src.query(criteria={"group": group}, properties=["value"]):
                new_max = max(new_max, rec["value"])
            self._src.tracking = True  # back to incremental mode
            # calculate new max
            self._groups[group] = new_max

    def finalize(self, errs):
        """Update target collection with calculated maximum values."""
        for group, value in self._groups.items():
            doc = {"group": group, "value": value}
            self._target_coll.update({"group": group}, doc, upsert=True)
        return True
