"""
Create and access groups of databases,
each configured from different settings.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "4/29/14"

import glob
import os
import re
from . import dbconfig, query_engine, util

# aliases
_opj = os.path.join
_opx = os.path.splitext


class CreateQueryEngineError(Exception):
    def __init__(self, cls, settings, err):
        msg = "creating query engine, class={cls} settings={s}: {m}".format(
            cls=cls.__name__, s=util.csv_dict(settings), m=err
        )
        Exception.__init__(self, msg)


class ConfigGroup:
    """Convenient storage and access to a group
    of database configurations.

    Will automatically instantiate these configurations,
    as query engines, on-demand.
    """

    SEP = "."  # Separator between collection names

    def __init__(self, qe_class=query_engine.QueryEngine):
        self._d = RegexDict()  # Main object store
        self._class = qe_class  # Class to used for building QEs
        self._pfx = None  # Prefix to namespace all lookups
        self._cached = {}  # cached QE objs

    def add_path(self, path, pattern="*.json"):
        """Add configuration file(s)
        in `path`. The path can be a single file or a directory.
        If path is a directory, then `pattern`
        (Unix glob-style) will be used to get a list of all config
        files in the directory.

        The name given to each file is the database name
        and collection name (if any) combined with a '.'.

        :param path: File or directory name
        :return: self, for chaining
        """
        if os.path.isdir(path):
            configs = glob.glob(_opj(path, pattern))
        else:
            configs = [path]
        for config in configs:
            cfg = dbconfig.DBConfig(config_file=config)
            cs = cfg.settings
            if dbconfig.DB_KEY not in cs:
                raise ValueError(f"No database in '{config}'")
            if dbconfig.COLL_KEY in cs:
                name = f"{cs[dbconfig.DB_KEY]}.{cs[dbconfig.COLL_KEY]}"
            else:
                name = cs[dbconfig.DB_KEY]
            self.add(name, cfg)
        return self

    def add(self, name, cfg, expand=False):
        """Add a configuration object.

        :param name: Name for later retrieval
        :param cfg: Configuration object
        :param expand: Flag for adding sub-configs for each sub-collection.
                       See discussion in method doc.
        :return: self, for chaining
        :raises: CreateQueryEngineError (only if expand=True)
        """
        self._d[name] = cfg
        if expand:
            self.expand(name)
        return self

    def expand(self, name):
        """Expand config for `name` by adding a sub-configuration for every
        dot-separated collection "below" the given one (or all, if none given).

        For example, for a database 'mydb' with collections
            ['spiderman.amazing', 'spiderman.spectacular', 'spiderman2']
        and a configuration
            {'host':'foo', 'database':'mydb', 'collection':'spiderman'}
        then `expand("mydb.spiderman")` would add keys for 'spiderman.amazing'
        and 'spiderman.spectacular', but *not* 'spiderman2'.

        :param name: Name, or glob-style pattern, for DB configurations.
        :type name: basestring
        :return: None
        :raises: KeyError (if no such configuration)
        """
        if self._is_pattern(name):
            expr = re.compile(self._pattern_to_regex(name))
            for cfg_name in self._d.keys():
                if expr.match(cfg_name):
                    self._expand(cfg_name)
        else:
            self._expand(name)

    def _expand(self, name):
        """Perform real work of `expand()` function."""
        cfg = self._d[name]
        if cfg.collection is None:
            base_coll = ""
        else:
            base_coll = cfg.collection + self.SEP
        qe = self._get_qe(name, cfg)
        coll, db = qe.collection, qe.db
        cur_coll = coll.name
        for coll_name in db.collection_names():
            if coll_name == cur_coll or not coll_name.startswith(base_coll):
                continue
            ex_cfg = cfg.copy()
            ex_cfg.collection = coll_name
            group_name = name + self.SEP + coll_name[len(base_coll) :]
            self.add(group_name, ex_cfg, expand=False)

    def uncache(self, name):
        """Remove all created query engines that match `name` from
        the cache (this disconnects from MongoDB, which is the point).

        :param name: Name used for :meth:`add`, or pattern
        :return: None
        """
        delme = []
        if self._is_pattern(name):
            expr = re.compile(self._pattern_to_regex(name))
            for key, obj in self._cached.items():
                if expr.match(key):
                    delme.append(key)
        else:
            if name in self._cached:
                delme.append(name)
        for key in delme:
            del self._cached[key]

    def __getitem__(self, name):
        """Dict-style lookup by name for
        query engine objects. If the input is a pattern,
        this will return a dict where keys are the names and values
        are the QueryEngine objects. Otherwise, will return a
        QueryEngine object. Raises a KeyError if there are no
        results (in either case).

        If this is the first time this query engine
        has been asked for, then it will instantiate the query engine.
        Errors here will raise CreateQueryEngineError.

        :param name: Name to look for; if it
                     ends in '*' then use it as a prefix
                     and return all matching items.
        :return: Single or multiple results (as dict)
        :raises: KeyError, CreateQueryEngineError
        """
        orig_name = name
        if self._pfx is not None:
            name = self._pfx + name
        if self._is_pattern(name):
            name = self._pattern_to_regex(name)
            # fill 'qe' with all items
            qe = {}
            for k, v in self._d.re_get(name).items():
                qe[k] = self._get_qe(k, v)
            if not qe:
                raise KeyError(f"No configuration found, name='{orig_name}' full-regex='{name}'")
        else:
            qe = self._get_qe(name, self._d[name])
        return qe

    def keys(self):
        return self._d.keys()

    def set_prefix(self, prefix=None):
        """Set prefix to use as a namespace for item lookup.
        A dot (.) will be automatically added to the given string.

        :param prefix: Prefix, or None to unset
        :return: None
        """
        if prefix is None:
            self._pfx = None
        else:
            self._pfx = prefix + self.SEP

    @staticmethod
    def _is_pattern(s):
        return s and (s[-1] == "*")

    @staticmethod
    def _pattern_to_regex(pat):
        pat = pat.replace(ConfigGroup.SEP, "\\" + ConfigGroup.SEP)
        return pat[:-1] + ".*"

    def _get_qe(self, key, obj):
        """Instantiate a query engine, or retrieve a cached one."""
        if key in self._cached:
            return self._cached[key]
        qe = create_query_engine(obj, self._class)
        self._cached[key] = qe
        return qe


class RegexDict(dict):
    """Extend standard dict to include
    a function that finds values based on a
    regular expression for the key. For example:

       d = RegexDict(tweedledee=1, tweedledum=2)

    """

    def re_keys(self, pattern):
        """Find keys matching `pattern`.

        :param pattern: Regular expression
        :return: Matching keys or empty list
        :rtype: list
        """
        if not pattern.endswith("$"):
            pattern += "$"
        expr = re.compile(pattern)
        return list(filter(expr.match, self.keys()))

    def re_get(self, pattern):
        """Return values whose key matches `pattern`

        :param pattern: Regular expression
        :return: Found values, as a dict.
        """
        return {k: self[k] for k in self.re_keys(pattern)}


def create_query_engine(config, clazz):
    """Create and return new query engine object from the
    given `DBConfig` object.

    :param config: Database configuration
    :type config: dbconfig.DBConfig
    :param clazz: Class to use for creating query engine. Should
                  act like query_engine.QueryEngine.
    :type clazz: class
    :return: New query engine
    """
    try:
        qe = clazz(**config.settings)
    except Exception as err:
        raise CreateQueryEngineError(clazz, config.settings, err)
    return qe
