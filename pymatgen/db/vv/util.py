"""
Utility functions and classes for validation.
"""
__author__ = "Dan Gunter"
__copyright__ = "Copyright 2012-2013, The Materials Project"
__version__ = "1.0"
__maintainer__ = "Dan Gunter"
__email__ = "dkgunter@lbl.gov"
__status__ = "Development"
__date__ = "3/29/13"

from argparse import Action
from collections import deque
from itertools import chain
import logging
import time
from sys import getsizeof
import ruamel.yaml as yaml

TRACE = logging.DEBUG - 1


class DoesLogging:
    """Mix-in class that creates the attribute 'log', setting its qualified
    name to the name of the module and class.
    """

    def __init__(self, name=None):
        if name is None:
            if self.__module__ != "__main__":
                name = f"{self.__module__}.{self.__class__.__name__}"
            else:
                name = self.__class__.__name__
        self._log = logging.getLogger(name)
        # cache whether log is debug or higher in a flag to
        # lower overhead of debugging statements
        self._dbg = self._log.isEnabledFor(logging.DEBUG)
        self._trace = self._log.isEnabledFor(TRACE)


def total_size(o, handlers={}, verbose=False, count=False):
    """Returns the approximate memory footprint an object and all of its contents.

    Automatically finds the contents of the following builtin containers and
    their subclasses:  tuple, list, deque, dict, set and frozenset.
    To search other containers, add handlers to iterate over their contents:

        handlers = {SomeContainerClass: iter,
                    OtherContainerClass: OtherContainerClass.get_elements}

    Source: http://code.activestate.com/recipes/577504/ (r3)
    """
    # How to make different types of objects iterable
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {
        tuple: iter,
        list: iter,
        deque: iter,
        dict: dict_handler,
        set: iter,
        frozenset: iter,
    }
    all_handlers.update(handlers)  # user handlers take precedence
    seen = set()  # track which object id's have already been seen
    default_size = getsizeof(0)  # estimate sizeof object without __sizeof__

    def sizeof(o):
        "Calculate size of `o` and all its children"
        if id(o) in seen:  # do not double count the same object
            return 0
        seen.add(id(o))
        if count:
            s = 1
        else:
            s = getsizeof(o, default_size)
        # If `o` is iterable, add size of its members
        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)


class ElapsedTime:
    def __init__(self):
        self.value = -1


class Timing:
    """Perform and report timings using the 'with' keyword.

    For example:
        with Timing('foo', info='bar'):
            do_foo1()
            do_foo2()
    """

    def __init__(self, name="event", elapsed=None, log=None, level=logging.DEBUG, **kwargs):
        self.name, self.kw, self.level = name, kwargs, level
        self.elapsed = elapsed
        self._log = log

    def __enter__(self):
        self.begin = time.time()

    def __exit__(self, type, value, tb):
        elapsed = time.time() - self.begin
        if self._log is not None:
            nvp = ", ".join([f"{k}={v}" for k, v in self.kw.items()])
            self._log.log(self.level, f"@{self.name}={elapsed:f}s {nvp}")
        if self.elapsed:
            self.elapsed.value = elapsed


def letter_num(x, letter="A"):
    s, a0 = "", ord(letter) - 1
    while x > 0:
        s = chr(a0 + x % 26) + s
        x /= 26
    return s


class JsonWalker:
    """Walk a dict, transforming.
    Used for JSON formatting.
    """

    def __init__(self, value_transform=None, dict_transform=None):
        """Constructor.

        :param value_transform: Apply this function to each value in a list or dict.
        :type value_transform: function taking a single arg (the value)
        :param dict_transform: Apply this function to each dict
        :type dict_transform: function taking a single arg (the dict)
        """
        self._vx = value_transform
        self._dx = dict_transform

    def walk(self, o):
        """Walk a dict & transform."""
        if isinstance(o, dict):
            d = o if self._dx is None else self._dx(o)
            return {k: self.walk(v) for k, v in d.items()}
        elif isinstance(o, list):
            return [self.walk(v) for v in o]
        else:
            return o if self._vx is None else self._vx(o)

    @staticmethod
    def value_json(o):
        """Apply as_json() method on object to get value,
        otherwise return object itself as the value.
        """
        if hasattr(o, "as_json"):
            return o.as_json()
        return o

    @staticmethod
    def dict_expand(o):
        """Expand keys in a dict with '.' in them into
        sub-dictionaries, e.g.

        {'a.b.c': 'foo'} ==> {'a': {'b': {'c': 'foo'}}}
        """
        r = {}
        for k, v in o.items():
            if isinstance(k, str):
                k = k.replace("$", "_")
            if "." in k:
                sub_r, keys = r, k.split(".")
                # create sub-dicts until last part of key
                for k2 in keys[:-1]:
                    sub_r[k2] = {}
                    sub_r = sub_r[k2]  # descend
                    # assign last part of key to value
                sub_r[keys[-1]] = v
            else:
                r[k] = v
        return r


# Argument handling
# -----------------

_alog = logging.getLogger("mg.args")
# _alog.setLevel(logging.DEBUG)
_argparse_is_dumb = True  # because it doesn't report orig. error text


class YamlConfig(Action):
    """Populate arguments with YAML file contents.

    Adapted from:
      http://code.activestate.com/recipes/577918-filling-command-line-arguments-with-a-file/
    """

    def __call__(self, parser, namespace, values, option_string=None):
        config = self._get_config_from_file(values)
        for key, value in config.items():
            setattr(namespace, key, value)
        _alog.debug(f"YamlConfig.namespace={namespace}")

    def _get_config_from_file(self, filename):
        with open(filename) as f:
            config = yaml.load(f)
        return config


def args_kvp_nodup(s):
    """Parse argument string as key=value pairs separated by commas.

    :param s: Argument string
    :return: Parsed value
    :rtype: dict
    :raises: ValueError for format violations or a duplicated key.
    """
    if s is None:
        return {}
    d = {}
    for item in [e.strip() for e in s.split(",")]:
        try:
            key, value = item.split("=", 1)
        except ValueError:
            msg = f"argument item '{item}' not in form key=value"
            if _argparse_is_dumb:
                _alog.warn(msg)
            raise ValueError(msg)
        if key in d:
            msg = f"Duplicate key for '{key}' not allowed"
            if _argparse_is_dumb:
                _alog.warn(msg)
            raise ValueError(msg)
        d[key] = value
    return d


def args_list(s):
    """Parse argument string as list of values separated by commas.

    :param s: Argument string
    :return: Parsed value
    :rtype: list
    """
    if s is None:
        return []
    return [item.strip() for item in s.split(",")]
