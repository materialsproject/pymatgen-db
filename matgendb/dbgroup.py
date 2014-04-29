"""
Create and access groups of databases,
each configured from different settings.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/29/14'

import glob
import os
import re
from . import dbconfig, query_engine

# aliases
_opj = os.path.join
_opx = os.path.splitext

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
    return clazz(**config.settings)

class QEGroup(object):
    """Convenient storage and access to a group
    of query engines.
    """
    def __init__(self, qe_class=query_engine.QueryEngine):
        self._d = RegexDict()
        self._class = qe_class
        self._pfx = None

    def add_path(self, path, pattern="*.json"):
        """Add query engines from configuration file(s)
        in `path`. The path can be a single file or a directory.
        If path is a directory, then `pattern`
        (Unix glob-style) will be used to get a list of all config
        files in the directory.

        The name given to each query engine is the database name
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
                qe = create_query_engine(cfg, self._class)
                cs = cfg.settings
                if dbconfig.DB_KEY not in cs:
                    raise ValueError("No database in '{}'".format(config))
                if dbconfig.COLL_KEY in cs:
                    name = "{}.{}".format(cs[dbconfig.DB_KEY],
                                          cs[dbconfig.COLL_KEY])
                else:
                    name = cs[dbconfig.DB_KEY]
                self.add(name, qe)
        return self

    def add(self, name, qe):
        """Add a query engine.

        :param name: Name for later retrieval
        :param qe: Query engine object
        :return: self, for chaining
        """
        self._d[name] = qe
        return self

    def __getitem__(self, name):
        """Dict-style lookup by name for
        query engine objects.

        :param name: Name to look for; if it
                     ends in '*' then use it as a prefix
                     and return all matching items.
        :return: Single or multiple results (as dict)
        """
        if self._pfx is not None:
            name = self._pfx + name
        if name and name[-1] == '*':
            name = name.replace(".", "\.")  # quote separator
            name = name[:-1] + ".*"
            return self._d.re_get(name)
        else:
            return self._d[name]

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
            self._pfx = prefix + '.'

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
        return filter(expr.match, self.iterkeys())

    def re_get(self, pattern):
        """Return values whose key matches `pattern`

        :param pattern: Regular expression
        :return: Found values, as a dict.
        """
        return {k: self[k] for k in self.re_keys(pattern)}
