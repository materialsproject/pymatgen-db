"""
Common functions for DB tests
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '10/29/13'

## Imports
# Stdlib
import os
# Package
from pymatpro.db.mongo.query_engine_mongo import MongoQueryEngine

## Classes and functions


def warn_no_db(log):
    log.warn("Error connecting to MongoDB. Some tests will be skipped.")


def skip_no_db(log, t):
    log.warn("Test '{}' skipped because of no DB".format(t))


class QueryEngine(MongoQueryEngine):
    def __init__(self, collection):
        MongoQueryEngine.__init__(self, database="test", host="localhost",
                                  collection=collection)
