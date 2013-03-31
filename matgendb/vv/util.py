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


def total_size(o, handlers={}, verbose=False):
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
        s = getsizeof(o, default_size)
        # If `o` is iterable, add size of its members
        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)
