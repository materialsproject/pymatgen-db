"""
Common utility functions for the database functions
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "11/4/13"

## Imports
import logging

# Stdlib
import os

# Local
import pymatgen

## Globals

## Functions and Classes


_top_dir = os.path.dirname(os.path.abspath(pymatgen.db.__file__))


def get_test_dir(name=None):
    """Get path to subdirectory with test files related
    to a given class.

    :param name: Name of class
    :return: Path
    :rtype: str
    """

    subdir = name + "_test"
    return os.path.join(_top_dir, "..", "test_files", subdir)


def get_schema_dir(db_version=1):
    """Get path to directory with schemata.

    :param db_version: Version of the database
    :type db_version: int
    :return: Path
    :rtype: str
    """
    v = str(db_version)
    return os.path.join(_top_dir, "..", "schemata", "versions", v)


def get_schema_file(db_version=1, db="mg_core", collection="materials"):
    """Get file with appropriate schema.

    :param db_version: Version of the database
    :type db_version: int
    :param db: Name of database, e.g. 'mg_core'
    :type db: str
    :param collection: Name of collection, e.g. 'materials'
    :type collection: str
    :return: File with schema
    :rtype: file
    :raise: IOError, if file is not found or not accessible
    """
    d = get_schema_dir(db_version=db_version)
    schemafile = f"{db}.{collection}.json"
    f = open(os.path.join(d, schemafile))
    return f


def get_builder_log(name):
    """Get a logging object, in the right place in the
    hierarchy, for a given builder.

    :param name: Builder name, e.g. 'my_builder'
    :type name: str
    :returns: New logger
    :rtype: logging.Logger
    """
    return logging.getLogger("mg.builders." + name)
