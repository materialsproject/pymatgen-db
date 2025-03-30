"""
A module for replicating the MP database creator.

See https://medium.com/@shyuep/a-local-materials-project-database-1ea909430c95
"""

from __future__ import annotations

import itertools

import pymongo

from pymatgen.entries.computed_entries import ComputedStructureEntry
from pymatgen.ext.matproj import MPRester


class MPDB:
    """This module allows you to create a local MP database based on ComputedStructureEntries."""

    def __init__(self, *args, **kwargs):
        """
        @param args: Pass through to MongoClient. E.g., you can create a connection using uri strings, etc.
        @param kwargs: Pass through to MongoClient. E.g., you can create a connection using uri strings, etc.
        """
        client = pymongo.MongoClient(*args, **kwargs)
        db = client.matproj
        self.collection = db.entries

    def create(self, criteria=None, property_data: list | None = None):
        """
        Creates the database. Typically only used once.

        @param criteria: Criteria passed to MPRester.get_entries to obtain the entries. None means you get the entire
            MP database.
        @param property_data: List of additional property data to obtain. These are stored in the data.* keys.
        """
        mpr = MPRester()
        criteria = criteria or {}
        property_data = property_data or []
        entries = mpr.get_entries(
            criteria,
            inc_structure=True,
            property_data=property_data,
        )
        docs = []
        for e in entries:
            comp = e.composition
            elements = sorted(e.composition.keys())
            elements_str = sorted([el.symbol for el in elements])
            d = e.as_dict()
            d["pretty_formula"] = comp.reduced_formula
            d["elements"] = elements_str
            d["nelements"] = len(comp)
            d["chemsys"] = "-".join(elements_str)
            docs.append(d)

        self.collection.insert_many(docs)

        # These create useful indexes to speed up querying.
        self.collection.create_index("entry_id")
        self.collection.create_index("pretty_formula")
        self.collection.create_index("chemsys")
        self.collection.create_index("nelements")
        self.collection.create_index("elements")

    def get_entries_in_chemsys(self, elements, additional_criteria=None):
        """
        Method get_entries_in_chemsys.

        Parameters:
        elements (str): A string of chemical elements separated by '-'. Can also be a list of chemical elements.
        additional_criteria (dict, optional): Additional criteria to filter entries. Default is None.

        Returns:
        list: A list of ComputedStructureEntry objects retrieved based on the given chemical systems and criteria.

        """
        if isinstance(elements, str):
            elements = elements.split("-")

        all_chemsyses = []
        for i in range(len(elements)):
            for els in itertools.combinations(elements, i + 1):
                all_chemsyses.append("-".join(sorted(els)))

        criteria = {"chemsys": {"$in": all_chemsyses}}
        if additional_criteria:
            criteria.update(additional_criteria)

        entries = []
        for r in self.collection.find(criteria):
            entries.append(ComputedStructureEntry.from_dict(r))

        return entries
