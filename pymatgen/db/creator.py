#!/usr/bin/env python

"""
This module defines a Drone to assimilate vasp data and insert it into a
Mongo database.
"""


import os
import re
import glob
import logging
import datetime
import string
import json
import socket
import numpy as np
import zlib
from fnmatch import fnmatch
from collections import OrderedDict

from pymongo import MongoClient
import gridfs

from pymatgen.apps.borg.hive import AbstractDrone
from pymatgen.analysis.local_env import VoronoiNN
from pymatgen.core.structure import Structure
from pymatgen.core.composition import Composition
from pymatgen.io.vasp import Vasprun, Incar, Kpoints, Potcar, Poscar, Outcar, Oszicar
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.bond_valence import BVAnalyzer
from monty.io import zopen
from pymatgen.ext.matproj import MPRester
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.analysis.structure_analyzer import oxide_type
from monty.json import MontyEncoder

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "2.0.0"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Mar 18, 2012"


logger = logging.getLogger(__name__)


class VaspToDbTaskDrone(AbstractDrone):
    """
    VaspToDbTaskDrone assimilates directories containing vasp input to
    inserted db tasks. This drone is meant ot be used with pymatgen's
    BorgQueen to assimilate entire directory structures and insert them into
    a database using Python's multiprocessing. The current format assumes
    standard VASP relaxation runs. If you have other kinds of runs,
    you may design your own Drone class based on this one.

    There are some restrictions on the valid directory structures:

        1. There can be only one vasp run in each directory. Nested directories
           are fine.
        2. Directories designated "relax1", "relax2" are considered to be
           2 parts of an aflow style run.
        3. Directories containing vasp output with ".relax1" and ".relax2" are
           also considered as 2 parts of an aflow style run.
    """

    # Version of this db creator document.
    __version__ = "2.0.0"

    def __init__(
        self,
        host="127.0.0.1",
        port=27017,
        database="vasp",
        user=None,
        password=None,
        collection="tasks",
        parse_dos=False,
        compress_dos=False,
        parse_projected_eigen=False,
        simulate_mode=False,
        additional_fields=None,
        update_duplicates=True,
        mapi_key=None,
        use_full_uri=True,
        runs=None,
    ):
        """Constructor.

        Args:
            host:
                Hostname of database machine. Defaults to 127.0.0.1 or
                localhost.
            port:
                Port for db access. Defaults to mongo's default of 27017.
            database:
                Actual database to access. Defaults to "vasp".
            user:
                User for db access. Requires write access. Defaults to None,
                which means no authentication.
            password:
                Password for db access. Requires write access. Defaults to
                None, which means no authentication.
            collection:
                Collection to query. Defaults to "tasks".
            parse_dos:
                Whether to parse the DOS data. Options are True, False, and 'final'
                Defaults to False. If True, all dos will be inserted into a gridfs
                collection called dos_fs. If 'final', only the last calculation will
                be parsed.
            parse_projected_eigen:
                Whether to parse the element and orbital projections. Options are True,
                False, and 'final'; Defaults to False. If True, projections will be
                parsed for each calculation. If 'final', projections for only the last
                calculation will be parsed.
            compress_dos:
                Whether to compress the DOS data. Valid options are integers 1-9,
                corresponding to zlib compression level. 1 is usually adequate.
            simulate_mode:
                Allows one to simulate db insertion without actually performing
                the insertion.
            additional_fields:
                Dict specifying additional fields to append to each doc
                inserted into the collection. For example, allows one to add
                an author or tags to a whole set of runs for example.
            update_duplicates:
                If True, if a duplicate path exists in the collection, the
                entire doc is updated. Else, duplicates are skipped.
            mapi_key:
                A Materials API key. If this key is supplied,
                the insertion code will attempt to use the Materials REST API
                to calculate stability data for inserted calculations.
                Stability assessment requires a large quantity of materials
                data. E.g., to compute the stability of a new LixFeyOz
                calculation, you need to the energies of all known
                phases in the Li-Fe-O chemical system. Using
                the Materials API, we can obtain the pre-calculated data from
                the Materials Project.

                Go to www.materialsproject.org/profile to generate or obtain
                your API key.
            use_full_uri:
                Whether to use full uri path (including hostname) for the
                directory name. Defaults to True. If False, only the abs
                path will be used.
            runs:
                Ordered list of runs to look for e.g. ["relax1", "relax2"].
                Automatically detects whether the runs are stored in the
                subfolder or file extension schema.
        """
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.collection = collection
        self.port = port
        self.simulate = simulate_mode
        if isinstance(parse_dos, str) and parse_dos != "final":
            raise ValueError("Invalid value for parse_dos")
        if isinstance(parse_projected_eigen, str) and parse_projected_eigen != "final":
            raise ValueError("Invalid value for parse_projected_eigen")
        self.parse_projected_eigen = parse_projected_eigen
        self.parse_dos = parse_dos
        self.compress_dos = compress_dos
        self.additional_fields = additional_fields or {}
        self.update_duplicates = update_duplicates
        self.mapi_key = mapi_key
        self.use_full_uri = use_full_uri
        self.runs = runs or ["relax1", "relax2"]
        if not simulate_mode:
            conn = MongoClient(self.host, self.port)
            db = conn[self.database]
            if self.user:
                db.authenticate(self.user, self.password)
            if db.counter.count_documents({"_id": "taskid"}) == 0:
                db.counter.insert_one({"_id": "taskid", "c": 1})

    def assimilate(self, path):
        """
        Parses vasp runs. Then insert the result into the db. and return the
        task_id or doc of the insertion.

        Returns:
            If in simulate_mode, the entire doc is returned for debugging
            purposes. Else, only the task_id of the inserted doc is returned.
        """
        try:
            d = self.get_task_doc(path)
            if self.mapi_key is not None and d["state"] == "successful":
                self.calculate_stability(d)
            tid = self._insert_doc(d)
            return tid
        except Exception as ex:
            import traceback

            logger.error(traceback.format_exc())
            return False

    def calculate_stability(self, d):
        m = MPRester(self.mapi_key)
        functional = d["pseudo_potential"]["functional"]
        syms = [f"{functional} {l}" for l in d["pseudo_potential"]["labels"]]
        entry = ComputedEntry(
            Composition(d["unit_cell_formula"]),
            d["output"]["final_energy"],
            parameters={"hubbards": d["hubbards"], "potcar_symbols": syms},
        )
        data = m.get_stability([entry])[0]
        for k in ("e_above_hull", "decomposes_to"):
            d["analysis"][k] = data[k]

    def get_task_doc(self, path):
        """
        Get the entire task doc for a path, including any post-processing.
        """
        logger.info(f"Getting task doc for base dir :{path}")
        files = os.listdir(path)
        vasprun_files = OrderedDict()
        if "STOPCAR" in files:
            # Stopped runs. Try to parse as much as possible.
            logger.info(path + " contains stopped run")
        for r in self.runs:
            if r in files:  # try subfolder schema
                for f in os.listdir(os.path.join(path, r)):
                    if fnmatch(f, "vasprun.xml*"):
                        vasprun_files[r] = os.path.join(r, f)
            else:  # try extension schema
                for f in files:
                    if fnmatch(f, f"vasprun.xml.{r}*"):
                        vasprun_files[r] = f
        if len(vasprun_files) == 0:
            for f in files:  # get any vasprun from the folder
                if fnmatch(f, "vasprun.xml*") and f not in vasprun_files.values():
                    vasprun_files["standard"] = f

        if len(vasprun_files) > 0:
            d = self.generate_doc(path, vasprun_files)
            if not d:
                d = self.process_killed_run(path)
            self.post_process(path, d)
        elif (not (path.endswith("relax1") or path.endswith("relax2"))) and contains_vasp_input(path):
            # If not Materials Project style, process as a killed run.
            logger.warning(path + " contains killed run")
            d = self.process_killed_run(path)
            self.post_process(path, d)
        else:
            raise ValueError("No VASP files found!")

        return d

    def _insert_doc(self, d):
        if not self.simulate:
            # Perform actual insertion into db. Because db connections cannot
            # be pickled, every insertion needs to create a new connection
            # to the db.
            conn = MongoClient(self.host, self.port)
            db = conn[self.database]
            if self.user:
                db.authenticate(self.user, self.password)
            coll = db[self.collection]

            # Insert dos data into gridfs and then remove it from the dict.
            # DOS data tends to be above the 4Mb limit for mongo docs. A ref
            # to the dos file is in the dos_fs_id.
            result = coll.find_one({"dir_name": d["dir_name"]}, ["dir_name", "task_id"])
            if result is None or self.update_duplicates:
                if self.parse_dos and "calculations" in d:
                    for calc in d["calculations"]:
                        if "dos" in calc:
                            dos = json.dumps(calc["dos"], cls=MontyEncoder)
                            if self.compress_dos:
                                dos = zlib.compress(dos.encode("utf-8"), self.compress_dos)
                                calc["dos_compression"] = "zlib"
                            fs = gridfs.GridFS(db, "dos_fs")
                            dosid = fs.put(dos)
                            calc["dos_fs_id"] = dosid
                            del calc["dos"]

                d["last_updated"] = datetime.datetime.today()
                if result is None:
                    if ("task_id" not in d) or (not d["task_id"]):
                        result = db.counter.find_one_and_update(filter={"_id": "taskid"}, update={"$inc": {"c": 1}})
                        d["task_id"] = result["c"]
                    logger.info("Inserting {} with taskid = {}".format(d["dir_name"], d["task_id"]))
                elif self.update_duplicates:
                    d["task_id"] = result["task_id"]
                    logger.info("Updating {} with taskid = {}".format(d["dir_name"], d["task_id"]))

                coll.update_one({"dir_name": d["dir_name"]}, {"$set": d}, upsert=True)
                return d["task_id"]
            else:
                logger.info("Skipping duplicate {}".format(d["dir_name"]))
        else:
            d["task_id"] = 0
            logger.info("Simulated insert into database for {} with task_id {}".format(d["dir_name"], d["task_id"]))
            return d

    def post_process(self, dir_name, d):
        """
        Simple post-processing for various files other than the vasprun.xml.
        Called by generate_task_doc. Modify this if your runs have other
        kinds of processing requirements.

        Args:
            dir_name:
                The dir_name.
            d:
                Current doc generated.
        """
        logger.info(f"Post-processing dir:{dir_name}")

        fullpath = os.path.abspath(dir_name)

        # VASP input generated by pymatgen's alchemy has a
        # transformations.json file that keeps track of the origin of a
        # particular structure. This is extremely useful for tracing back a
        # result. If such a file is found, it is inserted into the task doc
        # as d["transformations"]
        transformations = {}
        filenames = glob.glob(os.path.join(fullpath, "transformations.json*"))
        if len(filenames) >= 1:
            with zopen(filenames[0], "rt") as f:
                transformations = json.load(f)
                try:
                    m = re.match(r"(\d+)-ICSD", transformations["history"][0]["source"])
                    if m:
                        d["icsd_id"] = int(m.group(1))
                except Exception as ex:
                    logger.warning("Cannot parse ICSD from transformations " "file.")
                    pass
        else:
            logger.warning("Transformations file does not exist.")

        other_parameters = transformations.get("other_parameters")
        new_tags = None
        if other_parameters:
            # We don't want to leave tags or authors in the
            # transformations file because they'd be copied into
            # every structure generated after this one.
            new_tags = other_parameters.pop("tags", None)
            new_author = other_parameters.pop("author", None)
            if new_author:
                d["author"] = new_author
            if not other_parameters:  # if dict is now empty remove it
                transformations.pop("other_parameters")

        d["transformations"] = transformations

        # Calculations done using custodian has a custodian.json,
        # which tracks the jobs performed and any errors detected and fixed.
        # This is useful for tracking what has actually be done to get a
        # result. If such a file is found, it is inserted into the task doc
        # as d["custodian"]
        filenames = glob.glob(os.path.join(fullpath, "custodian.json*"))
        if len(filenames) >= 1:
            with zopen(filenames[0], "rt") as f:
                d["custodian"] = json.load(f)

        # Parse OUTCAR for additional information and run stats that are
        # generally not in vasprun.xml.
        try:
            run_stats = {}
            for filename in glob.glob(os.path.join(fullpath, "OUTCAR*")):
                outcar = Outcar(filename)
                i = 1 if re.search("relax2", filename) else 0
                taskname = "relax2" if re.search("relax2", filename) else "relax1"
                d["calculations"][i]["output"]["outcar"] = outcar.as_dict()
                run_stats[taskname] = outcar.run_stats
        except:
            logger.error(f"Bad OUTCAR for {fullpath}.")

        try:
            overall_run_stats = {}
            for key in [
                "Total CPU time used (sec)",
                "User time (sec)",
                "System time (sec)",
                "Elapsed time (sec)",
            ]:
                overall_run_stats[key] = sum(v[key] for v in run_stats.values())
            run_stats["overall"] = overall_run_stats
        except:
            logger.error(f"Bad run stats for {fullpath}.")

        d["run_stats"] = run_stats

        # Convert to full uri path.
        if self.use_full_uri:
            d["dir_name"] = get_uri(dir_name)

        if new_tags:
            d["tags"] = new_tags

        logger.info("Post-processed " + fullpath)

    def process_killed_run(self, dir_name):
        """
        Process a killed vasp run.
        """
        fullpath = os.path.abspath(dir_name)
        logger.info("Processing Killed run " + fullpath)
        d = {"dir_name": fullpath, "state": "killed", "oszicar": {}}

        for f in os.listdir(dir_name):
            filename = os.path.join(dir_name, f)
            if fnmatch(f, "INCAR*"):
                try:
                    incar = Incar.from_file(filename)
                    d["incar"] = incar.as_dict()
                    d["is_hubbard"] = incar.get("LDAU", False)
                    if d["is_hubbard"]:
                        us = np.array(incar.get("LDAUU", []))
                        js = np.array(incar.get("LDAUJ", []))
                        if sum(us - js) == 0:
                            d["is_hubbard"] = False
                            d["hubbards"] = {}
                    else:
                        d["hubbards"] = {}
                    if d["is_hubbard"]:
                        d["run_type"] = "GGA+U"
                    elif incar.get("LHFCALC", False):
                        d["run_type"] = "HF"
                    else:
                        d["run_type"] = "GGA"
                except Exception as ex:
                    print(str(ex))
                    logger.error(f"Unable to parse INCAR for killed run {dir_name}.")
            elif fnmatch(f, "KPOINTS*"):
                try:
                    kpoints = Kpoints.from_file(filename)
                    d["kpoints"] = kpoints.as_dict()
                except:
                    logger.error(f"Unable to parse KPOINTS for killed run {dir_name}.")
            elif fnmatch(f, "POSCAR*"):
                try:
                    s = Poscar.from_file(filename).structure
                    comp = s.composition
                    el_amt = s.composition.get_el_amt_dict()
                    d.update(
                        {
                            "unit_cell_formula": comp.as_dict(),
                            "reduced_cell_formula": comp.to_reduced_dict,
                            "elements": list(el_amt.keys()),
                            "nelements": len(el_amt),
                            "pretty_formula": comp.reduced_formula,
                            "anonymous_formula": comp.anonymized_formula,
                            "nsites": comp.num_atoms,
                            "chemsys": "-".join(sorted(el_amt.keys())),
                        }
                    )
                    d["poscar"] = s.as_dict()
                except:
                    logger.error(f"Unable to parse POSCAR for killed run {dir_name}.")
            elif fnmatch(f, "POTCAR*"):
                try:
                    potcar = Potcar.from_file(filename)
                    d["pseudo_potential"] = {
                        "functional": potcar.functional.lower(),
                        "pot_type": "paw",
                        "labels": potcar.symbols,
                    }
                except:
                    logger.error(f"Unable to parse POTCAR for killed run in {dir_name}.")
            elif fnmatch(f, "OSZICAR"):
                try:
                    d["oszicar"]["root"] = Oszicar(os.path.join(dir_name, f)).as_dict()
                except:
                    logger.error(f"Unable to parse OSZICAR for killed run in {dir_name}.")
            elif re.match(r"relax\d", f):
                if os.path.exists(os.path.join(dir_name, f, "OSZICAR")):
                    try:
                        d["oszicar"][f] = Oszicar(os.path.join(dir_name, f, "OSZICAR")).as_dict()
                    except:
                        logger.error("Unable to parse OSZICAR for killed " "run in {}.".format(dir_name))
        return d

    def process_vasprun(self, dir_name, taskname, filename):
        """
        Process a vasprun.xml file.
        """
        vasprun_file = os.path.join(dir_name, filename)
        if self.parse_projected_eigen and (self.parse_projected_eigen != "final" or taskname == self.runs[-1]):
            parse_projected_eigen = True
        else:
            parse_projected_eigen = False
        r = Vasprun(vasprun_file, parse_projected_eigen=parse_projected_eigen)
        d = r.as_dict()
        d["dir_name"] = os.path.abspath(dir_name)
        d["completed_at"] = str(datetime.datetime.fromtimestamp(os.path.getmtime(vasprun_file)))
        d["cif"] = str(CifWriter(r.final_structure))
        d["density"] = r.final_structure.density
        if self.parse_dos and (self.parse_dos != "final" or taskname == self.runs[-1]):
            try:
                d["dos"] = r.complete_dos.as_dict()
            except Exception:
                logger.warning(f"No valid dos data exist in {dir_name}.\n Skipping dos")
        if taskname == "relax1" or taskname == "relax2":
            d["task"] = {"type": "aflow", "name": taskname}
        else:
            d["task"] = {"type": taskname, "name": taskname}
        d["oxide_type"] = oxide_type(r.final_structure)
        return d

    def generate_doc(self, dir_name, vasprun_files):
        """
        Process aflow style runs, where each run is actually a combination of
        two vasp runs.
        """
        try:
            fullpath = os.path.abspath(dir_name)
            # Defensively copy the additional fields first.  This is a MUST.
            # Otherwise, parallel updates will see the same object and inserts
            # will be overridden!!
            d = {k: v for k, v in self.additional_fields.items()}
            d["dir_name"] = fullpath
            d["schema_version"] = VaspToDbTaskDrone.__version__
            d["calculations"] = [
                self.process_vasprun(dir_name, taskname, filename) for taskname, filename in vasprun_files.items()
            ]
            d1 = d["calculations"][0]
            d2 = d["calculations"][-1]

            # Now map some useful info to the root level.
            for root_key in [
                "completed_at",
                "nsites",
                "unit_cell_formula",
                "reduced_cell_formula",
                "pretty_formula",
                "elements",
                "nelements",
                "cif",
                "density",
                "is_hubbard",
                "hubbards",
                "run_type",
            ]:
                d[root_key] = d2[root_key]
            d["chemsys"] = "-".join(sorted(d2["elements"]))

            # store any overrides to the exchange correlation functional
            xc = d2["input"]["incar"].get("GGA")
            if xc:
                xc = xc.upper()
            d["input"] = {
                "crystal": d1["input"]["crystal"],
                "is_lasph": d2["input"]["incar"].get("LASPH", False),
                "potcar_spec": d1["input"].get("potcar_spec"),
                "xc_override": xc,
            }
            vals = sorted(d2["reduced_cell_formula"].values())
            d["anonymous_formula"] = {string.ascii_uppercase[i]: float(vals[i]) for i in range(len(vals))}
            d["output"] = {
                "crystal": d2["output"]["crystal"],
                "final_energy": d2["output"]["final_energy"],
                "final_energy_per_atom": d2["output"]["final_energy_per_atom"],
            }
            d["name"] = "aflow"
            p = d2["input"]["potcar_type"][0].split("_")
            pot_type = p[0]
            functional = "lda" if len(pot_type) == 1 else "_".join(p[1:])
            d["pseudo_potential"] = {
                "functional": functional.lower(),
                "pot_type": pot_type.lower(),
                "labels": d2["input"]["potcar"],
            }
            if len(d["calculations"]) == len(self.runs) or list(vasprun_files.keys())[0] != "relax1":
                d["state"] = "successful" if d2["has_vasp_completed"] else "unsuccessful"
            else:
                d["state"] = "stopped"
            d["analysis"] = get_basic_analysis_and_error_checks(d)

            sg = SpacegroupAnalyzer(Structure.from_dict(d["output"]["crystal"]), 0.1)
            d["spacegroup"] = {
                "symbol": sg.get_space_group_symbol(),
                "number": sg.get_space_group_number(),
                "point_group": sg.get_point_group_symbol(),
                "source": "spglib",
                "crystal_system": sg.get_crystal_system(),
                "hall": sg.get_hall(),
            }
            d["oxide_type"] = d2["oxide_type"]
            d["last_updated"] = datetime.datetime.today()
            return d
        except Exception as ex:
            import traceback

            print(traceback.format_exc())
            logger.error("Error in " + os.path.abspath(dir_name) + ".\n" + traceback.format_exc())

            return None

    def get_valid_paths(self, path):
        """
        There are some restrictions on the valid directory structures:

        1. There can be only one vasp run in each directory. Nested directories
           are fine.
        2. Directories designated "relax1", "relax2" are considered to be 2
           parts of an aflow style run.
        3. Directories containing vasp output with ".relax1" and ".relax2" are
           also considered as 2 parts of an aflow style run.
        """
        (parent, subdirs, files) = path
        if set(self.runs).intersection(subdirs):
            return [parent]
        if (
            not any([parent.endswith(os.sep + r) for r in self.runs])
            and len(glob.glob(os.path.join(parent, "vasprun.xml*"))) > 0
        ):
            return [parent]
        return []

    def convert(self, d):
        return d

    def __str__(self):
        return "VaspToDbDictDrone"

    @classmethod
    def from_dict(cls, d):
        return cls(**d["init_args"])

    def as_dict(self):
        init_args = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "collection": self.collection,
            "parse_dos": self.parse_dos,
            "simulate_mode": self.simulate,
            "additional_fields": self.additional_fields,
            "update_duplicates": self.update_duplicates,
        }
        output = {
            "name": self.__class__.__name__,
            "init_args": init_args,
            "version": __version__,
        }
        return output


def get_basic_analysis_and_error_checks(d, max_force_threshold=0.5, volume_change_threshold=0.2):

    initial_vol = d["input"]["crystal"]["lattice"]["volume"]
    final_vol = d["output"]["crystal"]["lattice"]["volume"]
    delta_vol = final_vol - initial_vol
    percent_delta_vol = delta_vol / initial_vol
    coord_num = get_coordination_numbers(d)
    calc = d["calculations"][-1]
    gap = calc["output"]["bandgap"]
    cbm = calc["output"]["cbm"]
    vbm = calc["output"]["vbm"]
    is_direct = calc["output"]["is_gap_direct"]

    warning_msgs = []
    error_msgs = []

    if abs(percent_delta_vol) > volume_change_threshold:
        warning_msgs.append(f"Volume change > {volume_change_threshold * 100}%")

    bv_struct = Structure.from_dict(d["output"]["crystal"])
    try:
        bva = BVAnalyzer()
        bv_struct = bva.get_oxi_state_decorated_structure(bv_struct)
    except ValueError as e:
        logger.error(f"Valence cannot be determined due to {e}.")
    except Exception as ex:
        logger.error(f"BVAnalyzer error {str(ex)}.")

    max_force = None
    if d["state"] == "successful" and d["calculations"][0]["input"]["parameters"].get("NSW", 0) > 0:
        # handle the max force and max force error
        max_force = max(np.linalg.norm(a) for a in d["calculations"][-1]["output"]["ionic_steps"][-1]["forces"])

        if max_force > max_force_threshold:
            error_msgs.append(f"Final max force exceeds {max_force_threshold} eV")
            d["state"] = "error"

        s = Structure.from_dict(d["output"]["crystal"])
        if not s.is_valid():
            error_msgs.append("Bad structure (atoms are too close!)")
            d["state"] = "error"

    return {
        "delta_volume": delta_vol,
        "max_force": max_force,
        "percent_delta_volume": percent_delta_vol,
        "warnings": warning_msgs,
        "errors": error_msgs,
        "coordination_numbers": coord_num,
        "bandgap": gap,
        "cbm": cbm,
        "vbm": vbm,
        "is_gap_direct": is_direct,
        "bv_structure": bv_struct.as_dict(),
    }


def contains_vasp_input(dir_name):
    """
    Checks if a directory contains valid VASP input.

    Args:
        dir_name:
            Directory name to check.

    Returns:
        True if directory contains all four VASP input files (INCAR, POSCAR,
        KPOINTS and POTCAR).
    """
    for f in ["INCAR", "POSCAR", "POTCAR", "KPOINTS"]:
        if not os.path.exists(os.path.join(dir_name, f)) and not os.path.exists(os.path.join(dir_name, f + ".orig")):
            return False
    return True


def get_coordination_numbers(d):
    """
    Helper method to get the coordination number of all sites in the final
    structure from a run.

    Args:
        d:
            Run dict generated by VaspToDbTaskDrone.

    Returns:
        Coordination numbers as a list of dict of [{"site": site_dict,
        "coordination": number}, ...].
    """
    structure = Structure.from_dict(d["output"]["crystal"])
    f = VoronoiNN()
    cn = []
    for i, s in enumerate(structure.sites):
        try:
            n = f.get_cn(structure, i)
            number = int(round(n))
            cn.append({"site": s.as_dict(), "coordination": number})
        except Exception:
            logger.error("Unable to parse coordination errors")
    return cn


def get_uri(dir_name):
    """
    Returns the URI path for a directory. This allows files hosted on
    different file servers to have distinct locations.

    Args:
        dir_name:
            A directory name.

    Returns:
        Full URI path, e.g., fileserver.host.com:/full/path/of/dir_name.
    """
    fullpath = os.path.abspath(dir_name)
    try:
        hostname = socket.gethostbyaddr(socket.gethostname())[0]
    except:
        hostname = socket.gethostname()
    return f"{hostname}:{fullpath}"
