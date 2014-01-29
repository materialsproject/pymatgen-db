"""
Porous materials builder.

XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXX WORK IN PROGRESS, DO NOT RUN XXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Example usage:
    src = MongoQueryEngine(..., collection='porous_materials')
    tgt = MongoQueryEngine(..., collection='materials')
    p = PorousMaterialsBuilder(source=src, target=tgt, ncores=12)
    status = p.run()
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '10/29/13'

## Imports

# Stdlib
import datetime
import json
import logging
import os
import re
# Package
from matgendb.builders.core import Builder

## Logging

logger = logging.getLogger('mg.' + __name__)

## Classes


class PorousMaterialsBuilder(Builder):
    """Add porous materials to the main materials collection.
    """
    def setup(self, source=None, target=None):
        """Set up for run

        :param source: The input porous materials collection
        :type source: QueryEngine
        :param target: The output materials collection
        :type target: QueryEngine
        """
        self._src, self._tgt = source, target
        self._counter = 0
        return self._src.query()

    def process_item(self, item):
        item = self._reformat(item)
        self._tgt.collection.insert(item)

    def finalize(self, errs):
        return True

    def _parsedt(self, s):
        return datetime.datetime.strptime(s[:s.find('.')], "%Y-%m-%d %H:%M:%S")

    def _reformat(self, item):
        curdate = datetime.datetime.now().isoformat()
        about = item['about']
        #iza = about['_ccsi']['IZA_code']
        created = self._parsedt(about['created_at']['string'])
        sites = item['sites']
        mmeta = item['material_metadata']
        mprop = item['material_properties']
        frm = mmeta['formula']
        elements = re.findall('[A-Z][a-z]?[0-9]*', frm)
        element_letters = [re.match("([A-Z][a-z]?).*", e).groups()[0] for e in elements]
        elements.sort()
        anon_frm_dict = {chr(ord('A') + i): float(re.match("[A-Z][a-z]?([0-9]*)", e).groups()[0])
                         for i, e in enumerate(elements)}
        anon_parts = ["{}{}".format(chr(ord('A') + i), int(re.match("[A-Z][a-z]?([0-9]*)", e).groups()[0]))
                      for i, e in enumerate(elements)]
        anon_frm = ''.join(anon_parts)
        reduced_frm = ' '.join(elements)
        chemsys = '-'.join(element_letters)
        iza_code = about['_ccsi']['IZA_code']
        snl_id = "zeo-{}".format(iza_code)
        d = {
            "task_id": "NA",
            "is_valid": True,
            "formula": frm,
            "snl_id": snl_id,
            "is_compatible": False,
            "is_hubbard": False,
            "updated_at": created,
            "encut": 0.0,
            "ntask_ids": 0,
            "oxide_type": "None",
            "ionic_steps": [],
            "hubbards": {},
            "task_ids": [],
            "task_type": "CCTBX optimize structure",
            "band_gap": {},
            "density": mprop['density'],
            "xrd": {},
            "delta_volume": 0.0,
            "nsites": len(sites),
            "structure": {
                "sites": item["sites"],
                "lattice": item["lattice"],
                "@class": "Structure",
                "@module": "pymatgen.core.structure"
            },
            "chemsys": '-'.join(elements),
            "pretty_formula": mmeta['formula'],
            "efermi": 0.0,
            "bv_structure": {},
            "anonymous_formula": anon_frm_dict,
            "run_type": "CCTBX",
            "snl_final": {
                'about': {
                    # TODO: look up in ICSD?
                    '_ccsi': about['_ccsi'],
                    'created_at': created,
                    'references': about['references'],
                    'authors': about['authors'],
                    'history': about['history'],
                    'projects': about['projects'],
                },
                'updated_at': curdate,
                "is_ordered": True,
                "is_valid": True,
                "reduced_cell_formula_abc": reduced_frm,
                "anonymized_formula": anon_frm,
                "chemsystem": chemsys,
                "formula": frm,
                "nelements": len(elements),
                "reduced_cell_formula": reduced_frm,
                "nsites": len(sites),
                "snl_id": snl_id,
                "snlgroup_key": snl_id
            },
            "reduced_cell_formula_abc": reduced_frm,
            "snlgroup_key": snl_id,
            "reduced_cell_formula": reduced_frm,
            "elements": elements,
            "nelements": len(elements),
            "anonymized_formula": anon_frm,
            "formation_energy_per_atom": 0.0,
            "is_ordered": True,
            "final_energy_per_atom": 0.0,
            "nkpts": 0,
            "initial_structure": {
                'lattice': item['lattice'],
            },
            "final_energy": 0.0,
            "full_formula": mmeta['formula'],
            "volume": item['lattice']['volume'],
            "spacegroup": {
                "icsd_name": "P 1",
                "number": 1,
                "cctbx_name": "P 1",
                "crystal_system": "none",
            },
        }
        # CIF
        if 'cif' in item:
            d['cif'] = item['cif']
        # Add custom properties
        container = d['porous'] = {}
        for prop_name in ('diffusion_coefficient', 'isotherms',  'thermo_parameters',
                          'material_properties', 'performance_data'):
            if prop_name in item:
                container[prop_name] = item[prop_name]
                # XXX: add @class and @module for pymatgen wrappers?
        # Done
        return d

    def examples(self):
        result = []
        input_dir = util.get_test_dir("porous")
        for input_file in ("porous_mat.json",):
            doc = json.load(open(os.path.join(input_dir, input_file), "r"))
            result.append(('materials', self._reformat(doc)))
        return result
