"""
This module provides a QueryEngine that simplifies queries for Mongo databases
generated using hive.
"""


__author__ = "Shyue Ping Ong, Michael Kocher, Dan Gunter"
__copyright__ = "Copyright 2011, The Materials Project"
__version__ = "2.0"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Production"
__date__ = "Mar 2 2013"

import itertools
import json
import logging
import os
import zlib
from collections import OrderedDict
from collections.abc import Iterable

import gridfs
import pymongo
from pymatgen.core import Composition, Structure
from pymatgen.electronic_structure.core import Orbital, Spin
from pymatgen.electronic_structure.dos import CompleteDos, Dos
from pymatgen.entries.computed_entries import ComputedEntry, ComputedStructureEntry

_log = logging.getLogger("mg." + __name__)


class QueryEngine:
    """This class defines a QueryEngine interface to a Mongo Collection based on
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
    ALIASES_CONFIG_KEY = "aliases_config"
    COLLECTION_KEY = "collection"
    HOST_KEY = "host"
    PORT_KEY = "port"
    DB_KEY = "database"
    USER_KEY = "user"
    PASSWORD_KEY = "password"

    # Aliases and defaults
    aliases = None  #: See `aliases` arg to constructor
    default_criteria = None  #: See `default_criteria` arg to constructor
    default_properties = None  #: See `default_properties` arg to constructor
    # Post-processing operations
    query_post = None  #: See `query_post` arg to constructor
    result_post = None  #: See `result_post` arg to constructor

    def __init__(
        self,
        host="127.0.0.1",
        port=27017,
        database="vasp",
        user=None,
        password=None,
        collection="tasks",
        aliases_config=None,
        default_properties=None,
        query_post=None,
        result_post=None,
        connection=None,
        replicaset=None,
        **ignore,
    ):
        """Constructor.

        Args:
            host (str): Hostname of database machine.
            port (int): Port for db access.
            database (str): Name of database to access.
            user (str): User for db access. `None` means no authentication.
            password (str): Password for db access. `None` means no auth.
            collection (str): Collection to query. Defaults to "tasks".
            connection (pymongo.Connection): If given, ignore 'host' and 'port'
                and use existing connection.
            aliases_config(dict):
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
                aliases (dict): Keys are the incoming property, values are the
                    property it will be translated to. This makes it easier
                    to organize the doc format in a way that is different from the
                    query format.
                defaults (dict): Criteria that should be applied
                    by default to all queries. For example, a collection may
                    contain data from both successful and unsuccessful runs but
                    for most querying purposes, you may want just successful runs
                    only. Note that defaults do not affect explicitly specified
                    criteria, i.e., if you suppy a query for {"state": "killed"},
                    this will override the default for {"state": "successful"}.
            default_properties (list): Property names (strings) to use by
                default, if no `properties` are given to query().
            query_post (list): Functions to post-process the `criteria` passed
                to `query()`, after aliases are resolved.
                Function takes two args, the criteria dict and list of
                result properties. Both may be modified in-place.
            result_post (list): Functions to post-process the cursor records.
                Function takes one arg, the document for the current record,
                that is modified in-place.
        """
        self.host = host
        self.port = port
        self.replicaset = replicaset
        self.database_name = database
        if connection is None:
            # can't pass replicaset=None to MongoClient (fails validation)
            if self.replicaset:
                self.connection = pymongo.MongoClient(self.host, self.port, replicaset=self.replicaset)
            else:
                self.connection = pymongo.MongoClient(self.host, self.port)
        else:
            self.connection = connection
        self.db = self.connection[database]
        if user:
            self.db.authenticate(user, password)
        self.collection_name = collection
        self.set_aliases_and_defaults(aliases_config=aliases_config, default_properties=default_properties)
        # Post-processing functions
        self.query_post = query_post or []
        self.result_post = result_post or []

    @property
    def collection_name(self):
        """
        Returns collection name.
        """
        return self._collection_name

    @collection_name.setter
    def collection_name(self, value):
        """Switch to another collection.
        Note that you may have to set the aliases and default properties if the
        schema of the new collection differs from the current collection.
        """
        self._collection_name = value
        self.collection = self.db[value]

    def set_aliases_and_defaults(self, aliases_config=None, default_properties=None):
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
            with open(os.path.join(os.path.dirname(__file__), "aliases.json")) as f:
                d = json.load(f)
                self.aliases = d.get("aliases", {})
                self.default_criteria = d.get("defaults", {})
        else:
            self.aliases = aliases_config.get("aliases", {})
            self.default_criteria = aliases_config.get("defaults", {})
        # set default properties
        if default_properties is None:
            self._default_props, self._default_prop_dict = None, None
        else:
            self._default_props, self._default_prop_dict = self._parse_properties(default_properties)

    def __enter__(self):
        """Allows for use with the 'with' context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Allows for use with the 'with' context manager"""
        self.close()

    def close(self):
        """Disconnects the connection."""
        self.connection.disconnect()

    def get_entries_in_system(
        self,
        elements,
        inc_structure=False,
        optional_data=None,
        additional_criteria=None,
    ):
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
            additional_criteria:
                Added ability to provide additional criteria other than just
                the chemical system.

        Returns:
            List of ComputedEntries in the chemical system.
        """
        chemsys_list = []
        for i in range(len(elements)):
            for combi in itertools.combinations(elements, i + 1):
                chemsys = "-".join(sorted(combi))
                chemsys_list.append(chemsys)
        crit = {"chemsys": {"$in": chemsys_list}}
        if additional_criteria is not None:
            crit.update(additional_criteria)
        return self.get_entries(crit, inc_structure, optional_data=optional_data)

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
        all_entries = []
        optional_data = [] if not optional_data else list(optional_data)
        optional_data.append("oxide_type")
        fields = list(optional_data)
        fields.extend(
            [
                "task_id",
                "unit_cell_formula",
                "energy",
                "is_hubbard",
                "hubbards",
                "pseudo_potential.labels",
                "pseudo_potential.functional",
                "run_type",
                "input.is_lasph",
                "input.xc_override",
                "input.potcar_spec",
            ]
        )
        if inc_structure:
            fields.append("output.crystal")

        for c in self.query(fields, criteria):
            func = c["pseudo_potential.functional"]
            labels = c["pseudo_potential.labels"]
            symbols = [f"{func} {label}" for label in labels]
            parameters = {
                "run_type": c["run_type"],
                "is_hubbard": c["is_hubbard"],
                "hubbards": c["hubbards"],
                "potcar_symbols": symbols,
                "is_lasph": c.get("input.is_lasph") or False,
                "potcar_spec": c.get("input.potcar_spec"),
                "xc_override": c.get("input.xc_override"),
            }
            optional_data = {k: c[k] for k in optional_data}
            if inc_structure:
                struct = Structure.from_dict(c["output.crystal"])
                entry = ComputedStructureEntry(
                    struct,
                    c["energy"],
                    0.0,
                    parameters=parameters,
                    data=optional_data,
                    entry_id=c["task_id"],
                )
            else:
                entry = ComputedEntry(
                    Composition(c["unit_cell_formula"]),
                    c["energy"],
                    0.0,
                    parameters=parameters,
                    data=optional_data,
                    entry_id=c["task_id"],
                )
            all_entries.append(entry)

        return all_entries

    def _parse_criteria(self, criteria):
        """
        Internal method to perform mapping of criteria to proper mongo queries
        using aliases, as well as some useful sanitization. For example, string
        formulas such as "Fe2O3" are auto-converted to proper mongo queries of
        {"Fe":2, "O":3}.

        If 'criteria' is None, returns an empty dict. Putting this logic here
        simplifies callers and allows subclasses to insert something even
        when there are no criteria.
        """
        if criteria is None:
            return {}
        parsed_crit = {}
        for k, v in self.default_criteria.items():
            if k not in criteria:
                parsed_crit[self.aliases.get(k, k)] = v

        for key, crit in list(criteria.items()):
            if key in ["normalized_formula", "reduced_cell_formula"]:
                comp = Composition(crit)
                parsed_crit["pretty_formula"] = comp.reduced_formula
            elif key == "unit_cell_formula":
                comp = Composition(crit)
                crit = comp.as_dict()
                for el, amt in crit.items():
                    parsed_crit[f"{self.aliases[key]}.{el}"] = amt
                parsed_crit["nelements"] = len(crit)
                parsed_crit["pretty_formula"] = comp.reduced_formula
            elif key in ["$or", "$and"]:
                parsed_crit[key] = [self._parse_criteria(m) for m in crit]
            else:
                parsed_crit[self.aliases.get(key, key)] = crit
        return parsed_crit

    def ensure_index(self, key, unique=False):
        """Wrapper for pymongo.Collection.ensure_index"""
        return self.collection.ensure_index(key, unique=unique)

    def query(self, properties=None, criteria=None, distinct_key=None, **kwargs):
        r"""
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
        :param distinct_key: If not None, the key for which to get distinct results
        :param \*\*kwargs: Other kwargs supported by pymongo.collection.find.
            Useful examples are limit, skip, sort, etc.
        :return: A QueryResults Iterable, which is somewhat like pymongo's
            cursor except that it performs mapping. In general, the dev does
            not need to concern himself with the form. It is sufficient to know
            that the results are in the form of an iterable of dicts.
        """
        if properties is not None:
            props, prop_dict = self._parse_properties(properties)
        else:
            props, prop_dict = None, None

        crit = self._parse_criteria(criteria)
        if self.query_post:
            for func in self.query_post:
                func(crit, props)
        cur = self.collection.find(filter=crit, projection=props, **kwargs)

        if distinct_key is not None:
            cur = cur.distinct(distinct_key)
            return QueryListResults(prop_dict, cur, postprocess=self.result_post)

        return QueryResults(prop_dict, cur, postprocess=self.result_post)

    def _parse_properties(self, properties):
        """Make list of properties into 2 things:
        (1) dictionary of { 'aliased-field': 1, ... } for a mongodb query eg. {''}
        (2) dictionary, keyed by aliased field, for display
        """
        props = {}
        # TODO: clean up prop_dict?
        prop_dict = OrderedDict()
        # We use a dict instead of list to provide for a richer syntax
        for p in properties:
            if p in self.aliases:
                if isinstance(properties, dict):
                    props[self.aliases[p]] = properties[p]
                else:
                    props[self.aliases[p]] = 1
                prop_dict[p] = self.aliases[p].split(".")
            else:
                if isinstance(properties, dict):
                    props[p] = properties[p]
                else:
                    props[p] = 1
                prop_dict[p] = p.split(".")
        # including a lower-level key after a higher level key e.g.:
        # {'output': 1, 'output.crystal': 1} instead of
        # {'output.crystal': 1, 'output': 1}
        # causes mongo to skip the other higher level keys.
        # this is a (sketchy) workaround for that. Note this problem
        # doesn't appear often in python2 because the dictionary ordering
        # is more stable.
        props = OrderedDict(sorted(props.items(), reverse=True))
        return props, prop_dict

    def query_one(self, *args, **kwargs):
        """Return first document from :meth:`query`, with same parameters."""
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
        args = {"task_id": task_id}
        field = "output.crystal" if final_structure else "input.crystal"
        results = tuple(self.query([field], args))

        if len(results) > 1:
            raise QueryError(f"More than one result found for task_id {task_id}!")
        if len(results) == 0:
            raise QueryError(f"No structure found for task_id {task_id}!")
        c = results[0]
        return Structure.from_dict(c[field])

    def __repr__(self):
        return f"QueryEngine: {self.host}:{self.port}/{self.database_name}"

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
            password = d["admin_password"] if use_admin else d["readonly_password"]
            return QueryEngine(
                host=d["host"],
                port=d["port"],
                database=d["database"],
                user=user,
                password=password,
                collection=d["collection"],
                aliases_config=d.get("aliases_config", None),
            )

    def __getitem__(self, item):
        """Support pymongo.Database syntax db['collection'] to access collections.
        Simply delegate this to the pymongo.Database instance, so behavior is the same.
        """
        return self.db[item]

    def get_dos_from_id(self, task_id):
        """
        Overrides the get_dos_from_id for the MIT gridfs format.
        """
        args = {"task_id": task_id}
        fields = ["calculations"]
        structure = self.get_structure_from_id(task_id)
        dosid = None
        for r in self.query(fields, args):
            dosid = r["calculations"][-1]["dos_fs_id"]
        if dosid is not None:
            self._fs = gridfs.GridFS(self.db, "dos_fs")
            with self._fs.get(dosid) as dosfile:
                s = dosfile.read()
                try:
                    d = json.loads(s)
                except Exception:
                    s = zlib.decompress(s)
                    d = json.loads(s.decode("utf-8"))
                tdos = Dos.from_dict(d)
                pdoss = {}
                for i in range(len(d["pdos"])):
                    ados = d["pdos"][i]
                    all_ados = {}
                    for j in range(len(ados)):
                        orb = Orbital(j)
                        odos = ados[str(orb)]
                        all_ados[orb] = {Spin(int(k)): v for k, v in odos["densities"].items()}
                    pdoss[structure[i]] = all_ados
                return CompleteDos(structure, tdos, pdoss)
        return None


class QueryResults(Iterable):
    """
    Iterable wrapper for results from QueryEngine.
    Like pymongo's cursor, this object should generally not be instantiated,
    but should be obtained from a queryengine.
    It delegates many attributes to the underlying pymongo cursor, and should
    support nearly all cursor like attributes such as count(), explain(),
    hint(), etc. Please see pymongo cursor documentation for details.
    """

    def __init__(self, prop_dict, result_cursor, postprocess=None):
        """Constructor.

        :param prop_dict: Properties
        :param result_cursor: Iterable returning records
        :param postprocess: List of functions, each taking a record and
            modifying it in-place, or None, or an empty list
        """
        self._results = result_cursor
        self._prop_dict = prop_dict
        self._pproc = postprocess or []  # make empty values iterable

    def _wrapper(self, func):
        """
        This function wraps all callable objects returned by self.__getattr__.
        If the result is a cursor, wrap it into a QueryResults object
        so that you can invoke postprocess functions in self._pproc
        """

        def wrapped(*args, **kwargs):
            ret_val = func(*args, **kwargs)
            if isinstance(ret_val, pymongo.cursor.Cursor):
                ret_val = self.from_cursor(ret_val)
            return ret_val

        return wrapped

    def __getattr__(self, attr):
        """
        Override getattr to make QueryResults inherit all pymongo cursor
        attributes.
        Wrap any callable object with _wrapper to intercept cursors and wrap them
        as a QueryResults object.
        """
        if hasattr(self._results, attr):
            ret_val = getattr(self._results, attr)
            # wrap callable objects to convert returned cursors into QueryResults
            if callable(ret_val):
                return self._wrapper(ret_val)
            return ret_val
        raise AttributeError

    def clone(self):
        """
        Provide a clone of the QueryResults.
        """
        return QueryResults(self._prop_dict, self._results.clone())

    def from_cursor(self, cursor):
        """
        Create a QueryResults object from a cursor object
        """
        return QueryResults(self._prop_dict, cursor, self._pproc)

    def __len__(self):
        """Return length as a `count()` on the MongoDB cursor."""
        return len(list(self._results.clone()))

    def __getitem__(self, i):
        return self._mapped_result(self._results[i])

    def __iter__(self):
        return self._result_generator()

    def _mapped_result(self, r):
        """Transform/map a result."""
        # Apply result_post funcs for pulling out sandbox properties
        for func in self._pproc:
            func(r)
        # If we haven't asked for specific properties, just return object
        if not self._prop_dict:
            result = r
        else:
            result = {}
            # Map aliased keys back to original key
            for k, v in self._prop_dict.items():
                try:
                    result[k] = self._mapped_result_path(v[1:], data=r[v[0]])
                except (IndexError, KeyError, ValueError):
                    result[k] = None
        return result

    @staticmethod
    def _mapped_result_path(path, data=None):
        if not path:
            return data
        if isinstance(data, list):
            return [QueryResults._mapped_result_path(path, d) for d in data]
        try:
            return QueryResults._mapped_result_path(path[1:], data[path[0]])
        except (IndexError, KeyError, ValueError):
            return None

    def _result_generator(self):
        for r in self._results:
            yield self._mapped_result(r)


class QueryListResults(QueryResults):
    """Set of QueryResults on a list instead of a MongoDB cursor."""

    def clone(self):
        """
        Return a clone of the QueryListResults.
        """
        return QueryResults(self._prop_dict, self._results[:])

    def __len__(self):
        """Return length of iterable, as a list if possible; otherwise,
        fall back to the superclass' implementation.
        """
        if hasattr(self._results, "__len__"):
            return len(self._results)
        return QueryResults.__len__(self)


class QueryError(Exception):
    """
    Exception class for errors occuring during queries.
    """

    pass
