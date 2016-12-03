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
def make_doc(ctx):
    with cd("docs"):
        ctx.run("cp ../CHANGES.rst change_log.rst")
        ctx.run("sphinx-apidoc -d 6 -o . -f ../matgendb")
        ctx.run("rm matgendb*.tests.rst")
        for f in glob.glob("*.rst"):
            if f.startswith('matgendb') and f.endswith('rst'):
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
                            if clean.startswith("pymatgen") and not clean.endswith("tests"):
                                newoutput.extend(suboutput)
                                subpackage = False
                                suboutput = []

                with open(f, 'w') as fid:
                    fid.write("".join(newoutput))
        ctx.run("make html")
        ctx.run("cp _static/* _build/html/_static")

        # Avoid ths use of jekyll so that _dir works as intended.
        ctx.run("touch _build/html/.nojekyll")


@task
def update_doc(ctx):
    with cd("docs/_build/html/"):
        ctx.run("git pull")
    make_doc(ctx)
    with cd("docs/_build/html/"):
        ctx.run("git add .")
        ctx.run("git commit -a -m \"Update dev docs\"")
        ctx.run("git push origin gh-pages")


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
    make_doc(ctx)
    publish(ctx)
