.. _dbconfig:

Database configuration
=======================

All the *pymatgen-db* database configuration files use JSON syntax.
They give the server host and port, as well as authentication parameters
for the database. If no authentication is given, then it is assumed
that the "noath" mode of MongoDB is to be used.

Here is an example configuration:

.. code-block:: json

    {
        host: "localhost",
        port: 27017,
        database: "vasp",
        readonly_user: "bigbird",
        readonly_password: "mr_snuffleupagus"
        collection: "tasks"
    }

The following keywords are recognized:

host
    Host name or IP of the database server. Required.
port
    Port number for database server. Default is 27017.
database
    Database name
readonly_user
    Authentication user name, for read-only access.
readonly_password
    Authentication password, for read-only access.
admin_user
    Authentication user name, for read/write access.
admin_password
    Authentication password, for read/write access.
