.. image:: https://travis-ci.org/materialsproject/pymatgen-db.png

Pymatgen-db is a database plugin for the Python Materials Genomics (pymatgen)
package.

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

The bleeding edge developmental version is at the pymatgen's `Github repo
<https://github.com/materialsproject/pymatgen>`_. The developmental
version is likely to be more buggy, but may contain new features. The
Github version include test files as well for complete unit testing. After
cloning the source, you can type::

    python setup.py install

or to install the package in developmental mode::

    python setup.py develop

The docs for the developmental version are available at pymatgen's `Github
pages <http://materialsproject.github.com/pymatgen/>`_.

Requirements
============

All required dependencies should be automatically taken care of if you
install pymatgen using easy_install or pip. Otherwise, these packages should
be available on `PyPI <http://pypi.python.org>`_.

1. Python 2.7+ required. New default modules such as json are used, as well as
   new unittest features in Python 2.7.
2. pymatgen 2.5+, including all dependencies associated with it.
3. pymongo 2.4+: For interfacing with MongoDb.

How to cite pymatgen
====================

If you use pymatgen in your research, please consider citing the following
work:

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
