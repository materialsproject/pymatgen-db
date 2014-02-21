Pymatgen-db
===========

Pymatgen-db is a database add-on for the `Python Materials Genomics
(pymatgen) <http://pymatgen.org>`_ materials analysis library. It enables
the creation of Materials Project-style `MongoDB`_ databases for management
of materials data. A query engine is also provided to enable the easy
translation of MongoDB docs to useful pymatgen objects for analysis purposes.

Pymatgen-db also provides a clean and intuitive web ui (the
`Materials Genomics UI`_) for exploring Mongo collections. While the design
originates for the purpose of exploring collections generated using
pymatgen-db, it can be used to explore any Mongo database and collection.

In addition, Pymatgen-db provides command-line tools for validation of MongoDB databases. Although these
tools are designed with the Materials Project databases in mind, they could be used
with almost any MongoDB database.

Change Log
==========

Version 0.3.9
-------------
#. `mgvv diff` HTML output can make they key field into a hyperlink using a user-provided prefix
#. Added brief introduction to `mgvv` in front page of Sphinx docs

Version 0.3.8
-------------
#. `mgvv diff` can perform numeric diffs. Better error handling.

Version 0.3.7
-------------
#. New package maintainer, Dan Gunter <dkgunter@lbl.gov>
#. Added `vv.diff` package and associated `mgvv diff` subcommand, for taking the difference of two arbitrary MongoDB collections.
#. Some cleanup and simplification of config files. `user` and `password` are accepted as aliases for `readonly_user` and `readonly_password`.


Version 0.3.4
-------------
1. MAPI_KEY is now a db config file variable.

Version 0.3.3
-------------

1. Minor bug fix release.

Version 0.3.2
-------------

1. Add option to use the Materials API to obtain stability data during run
   insertion.
2. Materials Genomics UI now supports setting a limit on number of results
   returned.
3. Improvements to mgdb script to allow setting of hosts, etc.

Version 0.3.0
-------------

1. Significant update to materials genomics ui. Ability to export table data
   to CSV, XLS or PDF.
2. First version of RESTful interface implemented.

:doc:`Older versions </changelog>`

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
are called mgvv and mgbuild respectively. Follow the links below for more
details on how to use and extend these programs:

.. toctree::
    :maxdepth: 1

    Database validation (mgvv) <mgvv>
    Database and sandbox creation (mgbuild) <mgbuild>

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

.. figure:: _static/mgui_dual_demo.png
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

Validating a database
----------------------

The :doc:`pymatgen-db validation script (mgvv) </mgvv>` is used to validate MongoDB databases.

Vhe basic usage of this command is::

    mgvv [options] 'constraints'

The constraints use a simplified syntax that was originally developed for this purpose, but has since
been moved into an independent package called smoqe_ .

.. _smoqe: https://pypi.python.org/pypi/smoqe/

The constraints can be placed in a YAML file so that complicated sets of constraints can be built up
and re-used. Results of validation can be formatted as plain text or HTML, and either printed to the
screen or emailed to a list of recipients.

In addition, there is a sub-command that does a "diff" of any two collections, looking for identifiers
that are missing from one or the other, or for mis-matching values for identifiers that are the same.

For example, if you want to compare the 'materials' collection in a development and production database.
You could have two JSON configuration files, `prod.json` and `dev.json` that specified the servers,
user and password, and database and collection names. These files have exactly the same format used
by the `mgdb` command-line tool.

You could issue this command-line::

    mgvv diff -k task_id  -p icsd_id -v -i pretty_formula mdev.json mprod.json

This compares with the key `task_id` and matches items with the same key on the property `icsd_id`, adding to the
output the value of the field `pretty_formula`. Because output is to the console, the format will default to text.

Like the main `mgvv` command, the results of database diffs can be formatted as text or HTML, and printed or emailed.

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

:doc:`pymatgen-db API docs </modules>`

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
