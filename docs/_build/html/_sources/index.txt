Pymatgen-db
===========

Pymatgen-db is a database add-on for the `Python Materials Genomics
(pymatgen) <http://pymatgen.org>`_ materials analysis library. It enables
the creation of Materials Project-style `MongoDB`_ databases for management
of materials data. A query engine is also provided to enable the easy
translation of MongoDB docs to useful pymatgen objects for analysis purposes.

Other pages
------------

.. toctree::
    :maxdepth: 1

    Validation and verification <mgvv>
    Building databases <builders>
    Configuration file format <dbconfig>
    API Reference <matgendb>

Change Log
==========

v0.6.2
------
* Minor bug fixes.

v0.6.1
------
* Removed Materials Genomics UI. Pls use Flamyngo as an alternative.

Getting pymatgen-db
===================

Stable version
--------------

The version at the Python Package Index (PyPI) is always the latest stable
release that will be hopefully, be relatively bug-free. The easiest way to
install pymatgen on any system is to use easy_install or pip, as follows::

    easy_install pymatgen-db

or::

    pip install pymatgen-db

Developmental version
---------------------

The bleeding edge developmental version is at the pymatgen-db's `Github repo`_.
The developmental version is likely to be more buggy, but may contain new
features. The Github version include test files as well for complete unit
testing. After cloning the source, you can type::

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
   to the `pymatgen docs <http://pymatgen.org>`_ for detailed
   installation instructions.
3. pymongo 2.4+: For interfacing with MongoDb.
4. MongoDB 2.2+: Get it at the `MongoDB`_ website.

Usage
=====

A powerful command-line script (mgdb) provides most of the access to many of
the features in pymatgen-db, including db initialization, insertion of data,
running the materials genomics ui, etc. To see all options available, type::

    mgdb --help

Validation and derived-database creation each use their own scripts, which
are called :doc:`mgvv <mgvv>` and :doc:`mgbuild <builders>`, respectively.


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
the "test_db" folder.

.. note::

    Running a Mongo server this way is insecure as Mongo does not enable
    authentication by default. Please refer to the `MongoDB manual`_ when
    setting up your production database.

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
defaults, etc., please refer to the following `sample <_static/db.json>`_.

Inserting calculations
----------------------

To insert an entire directory of runs (where the topmost directory is
"dir_name") into the database, use the following command::

    # Note that "-c db.json" may be omitted if the config filename is the
    # current directory under the default filename of db.json.

    mgdb insert -c db.json dir_name

A sample run has been provided for `download <_static/Li2O.zip>`_ for
testing purposes. Unzip the file and run the above command in the directory.

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

The format of the configuration file `db.json` is given :doc:`on this page <dbconfig>`.

For more advanced queries, you can use the
:class:`matgendb.query_engine.QueryEngine` class for which a default
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
:class:`matgendb.creator.VaspToDbTaskDrone` class as an example and write
similar drones for their needs. The
:class:`matgendb.query_engine.QueryEngine` can generally be applied to any
Mongo collection, with suitable specification of aliases if desired.

API/Reference Docs
==================

The API docs are generated using Sphinx auto-doc and outlines the purpose of all
modules and classes, and the expected argument and returned objects for most
methods. They are available at the link below.

:doc:`pymatgen-db API docs <matgendb>`

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

License
=======

Pymatgen-db is released under the MIT License. The terms of the license are as
follows::

    The MIT License (MIT)
    Copyright (c) 2011-2012 MIT & LBNL

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software")
    , to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _`MongoDB` : http://www.mongodb.org/
.. _`Github repo` : https://github.com/materialsproject/pymatgen-db
.. _`MongoDB manual` : http://docs.mongodb.org/manual/
