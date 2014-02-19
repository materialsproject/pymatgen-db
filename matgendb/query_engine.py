#!/usr/bin/env python

"""
This module provides a QueryEngine that simplifies queries for Mongo databases
generated using hive.
"""

from __future__ import division

__author__ = "Shyue Ping Ong, Michael Kocher"
__copyright__ = "Copyright 2011, The Materials Project"
__version__ = "2.0"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Production"
__date__ = "Mar 2 2013"

import json
import itertools
import logging
import os
from collections import OrderedDict, Iterable
from pymongo import MongoClient
from pymatgen import Structure, Composition
from pymatgen.entries.computed_entries import ComputedEntry,\
    ComputedStructureEntry

_log = logging.getLogger('mg.' + __name__)


class QueryEngine(object):
    """
    This class defines a QueryEngine interface to a Mongo Collection based on
    a set of aliases. This query engine also provides convenient translation
    between various pymatgen objects and database objects.

    The major difference between the QueryEngine's query() method and pymongo's
    find() method is the treatment of nested fields. QueryEngine's query
    will map the final result to a root level string, while pymmongo will
    return the doc as is. For example, let's say you have a document
    that is of the following form::

        {"a": {"b" : 1}}

    Using pymongo.find({}, fields=["a.b"]), you will get a doc where you need
    to do doc["a"]["b"] to access the final result (1). Using
    QueryEngine.query(properties=["a.b"], you will obtain a result that can be
    accessed simply as doc["a.b"].
    """

    # avoid hard-coding these in other places
    ALIASES_CONFIG_KEY = 'aliases_config'
    COLLECTION_KEY = 'collection'
    HOST_KEY = 'host'
    PORT_KEY = 'port'
    DB_KEY = 'database'
    USER_KEY = 'user'
    PASSWORD_KEY = 'password'

    def __init__(self, host="127.0.0.1", port=27017, database="vasp",
                 user=None, password=None, collection="tasks",
                 aliases_config=None, default_properties=None, **ignore):
        """
        Args:
            host:
                Hostname of database machine. Defaults to 127.0.0.1 or
                localhost.
            port:
                Port for db access. Defaults to mongo's default of 27017.
            database:
                Actual database to access. Defaults to "vasp".
            user:
                User for db access. Defaults to None, which means no
                authentication.
            password:
                Password for db access. Defaults to None, which means no
                authentication.
            collection:
                Collection to query. Defaults to "tasks".
            aliases_config:
                An alias dict to use. Defaults to None, which means the default
                aliases defined in "aliases.json" is used. The aliases config
                should be of the following format::

                    {
                        "aliases": {
                            "e_above_hull": "analysis.e_above_hull",
                            "energy": "output.final_energy",
                            ....
                        },
                        "defaults": {
                            "state": "successful"
                        }
                    }

                The "aliases" key defines mappings, which makes it easier to
                query for certain nested quantities. While Mongo does make it
                easy to map collections, it is sometimes beneficial to
                organize the doc format in a way that is different from the
                query format.
                The "defaults" key specifies criteria that should be applied
                by default to all queries. For example, a collection may
                contain data from both successful and unsuccessful runs but
                for most querying purposes, you may want just successful runs
                only. Note that defaults do not affect explicitly specified
                criteria, i.e., if you suppy a query for {"state": "killed"},
                this will override the default for {"state": "successful"}.
            default_properties:
                List of property names (strings) to use by default, if no
                properties are given to the 'properties' argument of
                query().
        """
        self.host = host
        self.port = port
        self.database_name = database
        self.collection_name = collection
        self.connection = MongoClient(self.host, self.port)
        self.db = self.connection[database]
        if user:
            self.db.authenticate(user, password)
        self.set_collection(collection=collection)
        self.set_aliases_and_defaults(aliases_config=aliases_config,
                                      default_properties=default_properties)

    def set_collection(self, collection):
        """
        Switch to another collection. Note that you may have to set the
        aliases and default properties via set_aliases_and_defaults if the
        schema of the new collection differs from the current collection.

        Args:
            collection:
                Name of collection.
        """
        self.collection = self.db[collection]

    def set_aliases_and_defaults(self, aliases_config=None,
                                 default_properties=None):
        """
        Set the alias config and defaults to use. Typically used when
        switching to a collection with a different schema.

        Args:
            aliases_config:
                An alias dict to use. Defaults to None, which means the default
                aliases defined in "aliases.json" is used. See constructor
                for format.
            default_properties:
                List of property names (strings) to use by default, if no
                properties are given to the 'properties' argument of
                query().
        """
        if aliases_config is None:
            with open(os.path.join(os.path.dirname(__file__),
                                   "aliases.json")) as f:
                d = json.load(f)
                self.aliases = d["aliases"]
                self.defaults = d["defaults"]
        else:
            self.aliases = aliases_config["aliases"]
            self.defaults = aliases_config["defaults"]
        # set default properties
        if default_properties is None:
            self._default_props, self._default_prop_dict = None, None
        else:
            self._default_props, self._default_prop_dict = \
                self._parse_properties(default_properties)

    def __enter__(self):
        """Allows for use with the 'with' context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Allows for use with the 'with' context manager"""
        self.close()

    def close(self):
        """Disconnects the connection."""
        self.connection.disconnect()

    def get_entries_in_system(self, elements, inc_structure=False,
                              optional_data=None):
        """
        Gets all entries in a chemical system, e.g. Li-Fe-O will return all
        Li-O, Fe-O, Li-Fe, Li-Fe-O compounds.

        .. note::

            The get_entries_in_system and get_entries  methods should be used
            with care. In essence, all entries, GGA, GGA+U or otherwise,
            are returned.  The dataset is very heterogeneous and not
            directly comparable.  It is highly recommended that you perform
            post-processing using pymatgen.entries.compatibility.

        Args:
            elements:
                Sequence of element symbols, e.g. ['Li','Fe','O']
            inc_structure:
                Optional parameter as to whether to include a structure with
                the ComputedEntry. Defaults to False. Use with care - including
                structures with a large number of entries can potentially slow
                down your code to a crawl.
            optional_data:
                Optional data to include with the entry. This allows the data
                to be access via entry.data[key].

        Returns:
            List of ComputedEntries in the chemical system.
        """
        chemsys_list = []
        for i in range(len(elements)):
            for combi in itertools.combinations(elements, i + 1):
                chemsys = "-".join(sorted(combi))
                chemsys_list.append(chemsys)
        crit = {"chemsys": {"$in": chemsys_list}}
        return self.get_entries(crit, inc_structure,
                                optional_data=optional_data)

    def get_entries(self, criteria, inc_structure=False, optional_data=None):
        """
        Get ComputedEntries satisfying a particular criteria.

        .. note::

            The get_entries_in_system and get_entries  methods should be used
            with care. In essence, all entries, GGA, GGA+U or otherwise,
            are returned.  The dataset is very heterogeneous and not
            directly comparable.  It is highly recommended that you perform
            post-processing using pymatgen.entries.compatibility.

        Args:
            criteria:
                Criteria obeying the same syntax as query.
            inc_structure:
                Optional parameter as to whether to include a structure with
                the ComputedEntry. Defaults to False. Use with care - including
                structures with a large number of entries can potentially slow
                down your code to a crawl.
            optional_data:
                Optional data to include with the entry. This allows the data
                to be access via entry.data[key].

        Returns:
            List of pymatgen.entries.ComputedEntries satisfying criteria.
        """
        all_entries = list()
        optional_data = [] if not optional_data else list(optional_data)
        fields = [k for k in optional_data]
        fields.extend(["task_id", "unit_cell_formula", "energy", "is_hubbard",
                       "hubbards", "pseudo_potential.labels",
                       "pseudo_potential.functional", "run_type"])
        for c in self.query(fields, criteria):
            func = c["pseudo_potential.functional"]
            labels = c["pseudo_potential.labels"]
            symbols = ["{} {}".format(func, label) for label in labels]
            parameters = {"run_type": c["run_type"],
                          "is_hubbard": c["is_hubbard"],
                          "hubbards": c["hubbards"],
                          "potcar_symbols": symbols}
            optional_data = {k: c[k] for k in optional_data}
            if inc_structure:
                struct = self.get_structure_from_id(c["task_id"])
                entry = ComputedStructureEntry(struct, c["energy"],
                                               0.0, parameters=parameters,
                                               data=optional_data,
                                               entry_id=c["task_id"])
            else:
                entry = ComputedEntry(Composition(c["unit_cell_formula"]),
                                      c["energy"], 0.0, parameters=parameters,
                                      data=optional_data,
                                      entry_id=c["task_id"])
            all_entries.append(entry)

        return all_entries

    def _parse_criteria(self, criteria):
        """
        Internal method to perform mapping of criteria to proper mongo queries
        using aliases, as well as some useful sanitization. For example, string
        formulas such as "Fe2O3" are auto-converted to proper mongo queries of
        {"Fe":2, "O":3}.
        """
        parsed_crit = dict()
        for k, v in self.defaults.items():
            if k not in criteria:
                parsed_crit[self.aliases.get(k, k)] = v

        for key, crit in list(criteria.items()):
            if key in ["normalized_formula", "reduced_cell_formula"]:
                comp = Composition(crit)
                parsed_crit["pretty_formula"] = comp.reduced_formula
            elif key == "unit_cell_formula":
                comp = Composition(crit)
                crit = comp.to_dict
                for el, amt in crit.items():
                    parsed_crit["{}.{}".format(self.aliases[key], el)] = amt
                parsed_crit["nelements"] = len(crit)
                parsed_crit['pretty_formula'] = comp.reduced_formula
            elif key in ["$or", "$and"]:
                parsed_crit[key] = [self._parse_criteria(m) for m in crit]
            else:
                parsed_crit[self.aliases.get(key, key)] = crit
        return parsed_crit

    def ensure_index(self, key, unique=False):
        """Wrapper for pymongo.Collection.ensure_index
        """
        return self.collection.ensure_index(key, unique=unique)

    def query(self, properties=None, criteria=None, index=0, limit=None, distinct_key=None):
        """
        Convenience method for database access.  All properties and criteria
        can be specified using simplified names defined in Aliases.  You can
        use the supported_properties property to get the list of supported
        properties.

        Results are returned as an iterator of dicts to ensure memory and cpu
        efficiency.

        Note that the dict returned have keys also in the simplified names
        form, not in the mongo format. For example, if you query for
        "analysis.e_above_hull", the returned result must be accessed as
        r['analysis.e_above_hull'] instead of mongo's
        r['analysis']['e_above_hull']. This is a *feature* of the query engine
        to allow simple access to deeply nested docs without having to resort
        to some recursion to go deep into the result.

        However, if you query for 'analysis', the entire 'analysis' key is
        returned as r['analysis'] and then the subkeys can be accessed in the
        usual form, i.e., r['analysis']['e_above_hull']

        :param properties: Properties to query for. Defaults to None which means all supported properties.
        :param criteria: Criteria to query for as a dict.
        :parm index: Similar definition to pymongo.collection.find method.
        :param limit: Similar definition to pymongo.collection.find method.
        :param distinct_key: If not None, the key for which to get distinct results
        :return: A QueryResults Iterable, which is somewhat like pymongo's
            cursor except that it performs mapping. In general, the dev does
            not need to concern himself with the form. It is sufficient to know
            that the results are in the form of an iterable of dicts.
        """
        if properties is not None:
            props, prop_dict = self._parse_properties(properties)
        else:
            props, prop_dict = None, None

        crit = self._parse_criteria(criteria) if criteria is not None else {}
        #print("@@ mongo query = {} and fields = {}".format(crit, props))
        cur = self.collection.find(crit, fields=props,
                                   timeout=False).skip(index)
        if limit is not None:
            cur.limit(limit)
        if distinct_key is not None:
            cur = cur.distinct(distinct_key)
            return QueryListResults(prop_dict, cur)
        else:
            return QueryResults(prop_dict, cur)

    def _parse_properties(self, properties):
        """Make list of properties into 2 things:
        (1) list of aliased fields for a mongodb query
        (2) dictionary, keyed by aliased field, for display
        """
        props = []
        prop_dict = OrderedDict()
        for p in properties:
            if p in self.aliases:
                props.append(self.aliases[p])
                prop_dict[p] = self.aliases[p].split(".")
            else:
                props.append(p)
                prop_dict[p] = p.split(".")
        return props, prop_dict

    def query_one(self, *args, **kwargs):
        """Return first document from :meth:`query`, with same parameters.
        """
        for r in self.query(*args, **kwargs):
            return r
        return None

    def get_structure_from_id(self, task_id, final_structure=True):
        """
        Returns a structure from the database given the task id.

        Args:
            task_id:
                The task_id to query for.
            final_structure:
                Whether to obtain the final or initial structure. Defaults to
                True.
        """
        args = {'task_id': task_id}
        field = 'output.crystal' if final_structure else 'input.crystal'
        results = tuple(self.query([field], args))

        if len(results) > 1:
            raise QueryError("More than one result found for task_id!")
        elif len(results) == 0:
            raise QueryError("No structure found for task_id!")
        c = results[0]
        return Structure.from_dict(c[field])

    def __repr__(self):
        return "QueryEngine: {}:{}/{}".format(self.host, self.port,
                                              self.database_name)

    @staticmethod
    def from_config(config_file, use_admin=False):
        """
        Initialize a QueryEngine from a JSON config file generated using mgdb
        init.

        Args:
            config_file:
                Filename of config file.
            use_admin:
                If True, the admin user and password in the config file is
                used. Otherwise, the readonly_user and password is used.
                Defaults to False.

        Returns:
            QueryEngine
        """
        with open(config_file) as f:
            d = json.load(f)
            user = d["admin_user"] if use_admin else d["readonly_user"]
            password = d["admin_password"] if use_admin \
                else d["readonly_password"]
            return QueryEngine(
                host=d["host"], port=d["port"], database=d["database"],
                user=user, password=password, collection=d["collection"],
                aliases_config=d.get("aliases_config", None))

    def __getitem__(self, item):
        """Support pymongo.Database syntax db['collection'] to access collections.
        Simply delegate this to the pymongo.Database instance, so behavior is the same.
        """
        return self.db[item]


class QueryResults(Iterable):
    """
    Iterable wrapper for results from QueryEngine.
    Like pymongo's cursor, this object should generally not be instantiated,
    but should be obtained from a queryengine.
    It delegates many attributes to the underlying pymongo cursor, and should
    support nearly all cursor like attributes such as count(), explain(),
    hint(), etc. Please see pymongo cursor documentation for details.
    """

    def __init__(self, prop_dict, result_cursor):
        self._results = result_cursor
        self._prop_dict = prop_dict

    def __getattr__(self, attr):
        """
        Override getattr to make QueryResults inherit all pymongo cursor
        attributes.
        """
        if hasattr(self._results, attr):
            return getattr(self._results, attr)

    def clone(self):
        return QueryResults(self._prop_dict, self._results.clone())

    def __len__(self):
        return self._results.count()

    def __getitem__(self, i):
        return self._mapped_result(self._results[i])

    def __iter__(self):
        return self._result_generator()

    def _mapped_result(self, r):
        if self._prop_dict is None:
            return r
        result = dict()
        for k, v in self._prop_dict.items():
            try:
                data = r[v[0]]
                for j in range(1, len(v)):
                    if isinstance(data, list):
                        data = [d[v[j]] for d in data]
                    else:
                        data = data[v[j]]
                result[k] = data
            except (IndexError, KeyError, ValueError):
                result[k] = None
        return result

    def _result_generator(self):
        for r in self._results:
            yield self._mapped_result(r)


class QueryListResults(QueryResults):
    """Set of QueryResults on a list instead of a MongoDB cursor.
    """

    def clone(self):
        return QueryResults(self._prop_dict, self._results[:])

    def __len__(self):
        return len(self._results)


class QueryError(Exception):
    """
    Exception class for errors occuring during queries.
    """
    pass
