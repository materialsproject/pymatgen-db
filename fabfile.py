#!/usr/bin/env python

"""
Deployment file to facilitate releases of matgendb.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Apr 29, 2012"

import glob
import os

from fabric.api import local, lcd
from matgendb import __version__ as ver


def makedoc():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "matgendb.webui.settings")
    with lcd("docs"):
        local("sphinx-apidoc -o . -f ../matgendb")
        local("rm matgendb*.tests.rst")
        for f in glob.glob("docs/*.rst"):
            if f.startswith('docs/matgendb') and f.endswith('rst'):
                newoutput = []
                suboutput = []
                subpackage = False
                with open(f, 'r') as fid:
                    for line in fid:
                        clean = line.strip()
                        if clean == "Subpackages":
                            subpackage = True
                        if not subpackage and not clean.endswith("tests"):
                            newoutput.append(line)
                        else:
                            if not clean.endswith("tests"):
                                suboutput.append(line)
                            if clean.startswith("matgendb") and not clean.endswith("tests"):
                                newoutput.extend(suboutput)
                                subpackage = False
                                suboutput = []

                with open(f, 'w') as fid:
                    fid.write("".join(newoutput))

        local("make html")
        local("cp favicon.ico ../../docs/pymatgen-db/html/static/favicon.ico")


def publish():
    local("python setup.py release")


def test():
    local("nosetests")


def setver():
    local("sed s/version=.*,/version=\\\"{}\\\",/ setup.py > newsetup".format(ver))
    local("mv newsetup setup.py")


def update_dev_doc():
    makedoc()
    with lcd("../docs/matgendb/html/"):
        local("git add .")
        local("git commit -a -m \"Update dev docs\"")
        local("git push origin gh-pages")


def release():
    setver()
    test()
    makedoc()
    publish()
