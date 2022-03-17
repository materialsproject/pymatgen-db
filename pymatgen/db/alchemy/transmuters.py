#!/usr/bin/env python

"""
This module implements a version of pymatgen's Transmuter to generate
TransformedStructures from DB data sources. They enable the
high-throughput generation of new structures and input files.
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Mar 4, 2012"

import datetime

from pymatgen.alchemy.materials import TransformedStructure
from pymatgen.alchemy.transmuters import StandardTransmuter


class QeTransmuter(StandardTransmuter):
    """
    The QeTransmuter uses a QueryEngine to retrieve and generate new structures
    from a database.
    """

    def __init__(self, queryengine, criteria, transformations, extend_collection=0, ncores=None):
        """Constructor.

        Args:
            queryengine:
                QueryEngine object for database access
            criteria:
                A criteria to search on, which is passed to queryengine's
                get_entries method.
            transformations:
                New transformations to be applied to all structures
            extend_collection:
                Whether to use more than one output structure from one-to-many
                transformations. extend_collection can be a number, which
                determines the maximum branching for each transformation.
            ncores:
                Number of cores to use for applying transformations.
                Uses multiprocessing.Pool
        """
        entries = queryengine.get_entries(criteria, inc_structure=True)

        source = f"{queryengine.host}:{queryengine.port}/{queryengine.database_name}/{queryengine.collection_name}"

        def get_history(entry):
            return [
                {
                    "source": source,
                    "criteria": criteria,
                    "entry": entry.as_dict(),
                    "datetime": datetime.datetime.utcnow(),
                }
            ]

        transformed_structures = [
            TransformedStructure(entry.structure, [], history=get_history(entry)) for entry in entries
        ]
        StandardTransmuter.__init__(
            self,
            transformed_structures,
            transformations=transformations,
            extend_collection=extend_collection,
            ncores=ncores,
        )
