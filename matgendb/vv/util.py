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

import time
import logging
from sys import getsizeof, stderr
from itertools import chain
from collections import deque

TRACE = logging.DEBUG -1


class DoesLogging:
    """Mix-in class that creates the attribute 'log', setting its qualified
    name to the name of the module and class.
    """
    def __init__(self, name=None):
        if name is None:
            if self.__module__ != '__main__':
                name = "%s.%s" % (self.__module__, self.__class__.__name__)
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
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter}
    all_handlers.update(handlers)     # user handlers take precedence
    seen = set()                      # track which object id's have already been seen
    default_size = getsizeof(0)       # estimate sizeof object without __sizeof__

    def sizeof(o):
        "Calculate size of `o` and all its children"
        if id(o) in seen:             # do not double count the same object
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

class ElapsedTime(object):
    def __init__(self):
        self.value = -1

class Timing(object):
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
            nvp = ', '.join(['{}={}'.format(k, v) for k, v in self.kw.iteritems()])
            self._log.log(self.level, '@{n}={s:f}s {kw}'.format(n=self.name, s=elapsed, kw=nvp))
        if self.elapsed:
            self.elapsed.value = elapsed


def letter_num(x, letter='A'):
    s, a0 = '', ord(letter) - 1
    while x > 0:
        s = chr(a0 + x % 26) + s
        x /= 26
    return s