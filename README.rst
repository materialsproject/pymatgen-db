Pymatgen-db is a database add-on for the Python Materials Genomics (pymatgen)
materials analysis library. It enables the creation of Materials
Project-style `MongoDB`_ databases for management of materials data. A query
engine is also provided to enable the easy translation of MongoDB docs to
useful pymatgen objects for analysis purposes.

Pymatgen-db also provides a clean and intuitive web ui (the
`Materials Genomics UI`_) for exploring Mongo collections. While the design
originates for the purpose of exploring collections generated using
pymatgen-db, it can be used to explore any Mongo database and collection.

Getting pymatgen-db
===================

Stable version
--------------

The version at the Python Package Index (PyPI) is always the latest stable
release that will be hopefully, be relatively bug-free. The easiest way to
install pymatgen-db on any system is to use easy_install or pip, as follows::

    easy_install pymatgen-db

or::

    pip install pymatgen-db

Developmental version
---------------------

The bleeding edge developmental version is at the pymatgen-db's `Github repo
<https://github.com/materialsproject/pymatgen-db>`_. The developmental
version is likely to be more buggy, but may contain new features. The
Github version include test files as well for complete unit testing. After
cloning the source, you can type::

    python setup.py install

or to install the package in developmental mode::

    python setup.py develop

Requirements
============

All required python dependencies should be automatically taken care of if you
install pymatgen-db using easy_install or pip. Otherwise, these packages should
be available on `PyPI <http://pypi.python.org>`_.

1. Python 2.7+ required. New default modules such as json are used, as well as
   new unittest features in Python 2.7.
2. pymatgen 2.5+, including all dependencies associated with it. Please refer
   to the `pymatgen docs <http://pythonhosted.org//pymatgen>`_ for detailed
   installation instructions.
3. pymongo 2.4+: For interfacing with MongoDb.
4. MongoDB 2.2+: Get it at the `MongoDB`_ website.

Usage
=====

A powerful command-line script (mgdb) provides most of the access to many of
the features in pymatgen-db, including db initialization, insertion of data,
running the materials genomics ui, etc. To see all options available, type::

    mgdb --help

Initial setup
-------------

The first step is to install and setup MongoDB on a server of your choice.
The `MongoDB manual`_ is an excellent place to start. For the purposes of
testing out the tools here, you may simply download the binary distributions
corresponding to your OS from the `MongoDB`_ website, and then running the
following commands::

    # For Mac and Linux OS.
    mkdir test_db && mongod --dbpath test_db

This will create a test database and start the Mongo daemon. Once you are
done with testing, you can simply press Ctrl-C to stop the server and delete
the "test_db" folder. Running a Mongo server this way is insecure as Mongo
does not enable authentication by default. Please refer to the `MongoDB
manual`_ when setting up your production database.

After your server is up, you should create a database config file by running
the following command::

    mgdb init -c db.json


This will prompt you for a few parameters to create a database config file,
which will make it much easier to use mgdb in future. Note that the config file
name can be anything of your choice, but using "db.json" will allow you to use
mgdb without explicitly specifying the filename in future. If you are just
testing using the test database, simply hit Enter to accept the defaults for
all settings.

For more advanced use of the "db.json" config file (e.g., specifying aliases,
defaults, etc., please refer to the following `sample
<http://pythonhosted.org/pymatgen-db/static/db.json>`_.

Inserting calculations
----------------------

To insert an entire directory of runs (where the topmost directory is
"dir_name") into the database, use the following command::

    # Note that "-c db.json" may be omitted if the config filename is the
    # current directory under the default filename of db.json.

    mgdb insert -c db.json dir_name

A sample run has been provided for `download
<http://pythonhosted.org/pymatgen-db/static/Li2O.zip>`_ for testing
purposes. Unzip the file and run the above command in the directory.

Materials Genomics UI
---------------------

A simple web interface has been provided to assist in the querying and
viewing of results. This web interface can be started by running::

    mgdb runserver -c db.json

This will run the web server at http://127.0.0.1:8000. Go to this address in
your browser and you should see something like the figure below. Most queries
can be performed using the web ui. Two options for presenting results are
provided - a table format which is easier for comparing data,
and a tree format which makes it much easier to explore highly nested trees
of data.

.. figure:: http://pythonhosted.org/pymatgen-db/_images/mgui_dual_demo.png
    :width: 100%
    :alt: materials genomics ui
    :align: center

    materials genomics ui

Materials Genomics RESTful API
------------------------------

The Materials Genomics UI also implements a RESTful interface to the database.
Two main methods are implemented now. A simple GET request that provides the
ability to delve into a document. For example::

    http://127.0.0.1:8000/rest/14/output

returns the "output" key of task_id 14 as a JSON.

A more advanced POST request provides the ability to make advanced queries.
This is the basis upon which the Materials Genomics UI is built. For example,
posting::

    {criteria: "criteria as json string",
     properties: "list of properties as json string"}

to::

    http://127.0.0.1:8000/rest/query

would return the query as a JSON response.

Querying a database
-------------------

Sometimes, more fine-grained querying is needed (e.g., for subsequent
postprocessing and analysis).

The mgdb script allows you to make simple queries from the command line::

    # Query for the task id and energy per atom of all calculations with
    # formula Li2O. Note that the criteria has to be specified in the form of
    # a json string. Note that "-c db.json" may be omitted if the config
    # filename is the current directory under the default filename of db.json.

    mgdb query -c db.json --crit '{"pretty_formula": "Li2O"}' --props task_id energy_per_atom

For more advanced queries, you can use the QueryEngine class for which an
alias is provided at the root package. Some examples are as follows::

    >>> from matgendb import QueryEngine
    >>> qe = QueryEngine()

    #Print the task id and formula of all entries in the database.
    >>> for r in qe.query(properties=["pretty_formula", "task_id"]):
    ...     print "{task_id} - {pretty_formula}".format(**r)
    ...
    12 - Li2O

    # Get a pymatgen Structure from the task_id.
    >>> structure = qe.get_structure_from_id(12)

    # Get pymatgen ComputedEntries using a criteria.
    >>> entries = qe.get_entries({})

The language follows very closely to pymongo/MongoDB syntax, except that
QueryEngine provides useful aliases for commonly used fields as well as
translation to commonly used pymatgen objects like Structure and
ComputedEntries.

Extending pymatgen-db
---------------------

Currently, pymatgen-db is written with standard VASP runs in mind. However,
it is perfectly extensible to any kind of data, e.g., other kinds of VASP runs
(bandstructure, NEB, etc.) or just any form of data in general. Developers
looking to adapt pymatgen-db for other purposes should look at the
VaspToDbTaskDrone class as an example and write similar drones for their
needs. The QueryEngine can generally be applied to any Mongo collection,
with suitable specification of aliases if desired.

How to cite pymatgen-db
=======================

If you use pymatgen and pymatgen-db in your research, please consider citing
the following work:

    Shyue Ping Ong, William Davidson Richards, Anubhav Jain, Geoffroy Hautier,
    Michael Kocher, Shreyas Cholia, Dan Gunter, Vincent Chevrier, Kristin A.
    Persson, Gerbrand Ceder. *Python Materials Genomics (pymatgen) : A Robust,
    Open-Source Python Library for Materials Analysis.* Computational
    Materials Science, 2013, 68, 314-319. `doi:10.1016/j.commatsci.2012.10.028
    <http://dx.doi.org/10.1016/j.commatsci.2012.10.028>`_

.. _`MongoDB` : http://www.mongodb.org/
.. _`Github repo` : https://github.com/materialsproject/pymatgen-db
.. _`MongoDB manual` : http://docs.mongodb.org/manual/