# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
from io import open

from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()

setup(
    name="pymatgen-db",
    packages=find_packages(),
    version="0.6.5",
    setup_requires=["numpy"],
    install_requires=["pymatgen>=4.4.9", "monty>=0.9.6", "pymongo>=2.8", "smoqe"],
    extras_require={
        ':python_version == "2.7"': [
            'enum34',
        ],
        'tests': 'mongomock'
    },
    package_data={"matgendb": ["*.json"]},
    author="Shyue Ping Ong, Dan Gunter",
    author_email="shyuep@gmail.com",
    maintainer="Dan Gunter",
    maintainer_email="dkgunter@lbl.gov",
    url="https://github.com/materialsproject/pymatgen-db",
    license="MIT",
    description="Pymatgen-db is a database add-on for the Python Materials "
                "Genomics (pymatgen) materials analysis library.",
    long_description=long_desc,
    keywords=["vasp", "gaussian", "materials", "project", "electronic",
              "structure", "mongo"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database"
    ],
    scripts=[os.path.join("scripts", f) for f in os.listdir("scripts")
             if not os.path.isdir(os.path.join("scripts", f))]
)
