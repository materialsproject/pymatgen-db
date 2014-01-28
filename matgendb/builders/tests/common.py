"""
Common functions for DB tests
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '10/29/13'

from mongomock import MongoClient
from matgendb.query_engine import QueryEngine


class MockQueryEngine(QueryEngine):
    """Mock (fake) QueryEngine, unless a real connection works.
    """
    def __init__(self, host="127.0.0.1", port=27017, database="vasp",
                 user=None, password=None, collection="tasks",
                 aliases_config=None, default_properties=None):
        try:
            QueryEngine.__init__(self, host=host, port=port, database=database,
                                 user=user, password=password, collection=collection,
                                 aliases_config=aliases_config,
                                 default_properties=default_properties)
            print("@@ connected to real Mongo")
            return  # actully connected! not mocked..
        except:
            pass
        self.connection = MongoClient(self.host, self.port)
        self.db = self.connection[database]
        self._user, self._password = user, password
        self.host = host
        self.port = port
        self.database_name = database
        self.collection_name = collection
        self.set_collection(collection=collection)
        self.set_aliases_and_defaults(aliases_config=aliases_config,
                                      default_properties=default_properties)
