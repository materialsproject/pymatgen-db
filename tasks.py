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

from invoke import task
from monty.os import cd
from matgendb import __version__ as ver


@task
def makedoc(ctx):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "matgendb.webui.settings")
    with cd("docs"):
        ctx.run("sphinx-apidoc -o . -f ../matgendb")
        ctx.run("rm matgendb*.tests.rst")
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

        ctx.run("make html")
        ctx.run("cp favicon.ico _build/html/_static/favicon.ico")


@task
def publish(ctx):
    ctx.run("python setup.py release")


@task
def test(ctx):
    ctx.run("nosetests")


@task
def setver(ctx):
    ctx.run("sed s/version=.*,/version=\\\"{}\\\",/ setup.py > newsetup".format(ver))
    ctx.run("mv newsetup setup.py")


@task
def release(ctx):
    setver(ctx)
    #test(ctx)
    makedoc(ctx)
    publish(ctx)
