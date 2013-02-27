.. image:: https://travis-ci.org/materialsproject/pymatgen-db.png

Pymatgen-db is a database plugin for the Python Materials Genomics (pymatgen)
package. It enables the creation of Materials Project-style databases for
management of materials data.

For now, the creation of a `MongoDB`_ database is supported and a rudimentary
query engine is provided to enable the easy translation of MongoDB docs to
useful pymatgen objects for analysis purposes. A simple web-based interface is
planned for the future.

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
be available on `PyPI <http://pypi.python.org>`_. Please note that if you do
not already have pymatgen installed, you should refer to the `pymatgen docs
<http://pythonhosted.org//pymatgen>`_ for detailed instructions.

1. Python 2.7+ required. New default modules such as json are used, as well as
   new unittest features in Python 2.7.
2. pymatgen 2.5+, including all dependencies associated with it.
3. pymongo 2.4+: For interfacing with MongoDb.
4. MongoDB 2.2+: Get it at the `MongoDB`_ website.

Usage
=====

A db creation/insertion script has been written (insert_into_db.py) has been
written and will be automatically installed as part of the installation
process. Type::

    insert_into_db.py --help

to see all the options. Typically, to insert an entire directory of runs into
the database, all you need to do is::

    insert_into_db.py -d DATABASE_HOST -b DATABASE_NAME -u USER -p PASSWORD dir_name

How to cite pymatgen
====================

If you use pymatgen and pymatgen-db in your research, please consider citing
the following work:

    Shyue Ping Ong, William Davidson Richards, Anubhav Jain, Geoffroy Hautier,
    Michael Kocher, Shreyas Cholia, Dan Gunter, Vincent Chevrier, Kristin A.
    Persson, Gerbrand Ceder. *Python Materials Genomics (pymatgen) : A Robust,
    Open-Source Python Library for Materials Analysis.* Computational
    Materials Science, 2013, 68, 314-319. `doi:10.1016/j.commatsci.2012.10.028
    <http://dx.doi.org/10.1016/j.commatsci.2012.10.028>`_

In addition, some of pymatgen's functionality is based on scientific advances
/ principles developed by the computational materials scientists in our team.
Please refer to `pymatgen's documentation
<http://pythonhosted.org/pymatgen/>`_ on how to cite them.

.. _`MongoDB` : http://www.mongodb.org/
