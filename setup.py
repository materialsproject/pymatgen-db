# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.
"""Setup file for pymatgen-db."""
from __future__ import annotations

import os

from setuptools import find_namespace_packages, setup

with open("README.rst") as f:
    long_desc = f.read()

setup(
    name="pymatgen-db",
    packages=find_namespace_packages(include=["pymatgen.*"]),
    version="2023.7.18",
    setup_requires=["numpy"],
    install_requires=["pymatgen>=2022.0.3", "monty>=0.9.6", "pymongo>=2.8"],
    extras_require={"tests": "mongomock"},
    package_data={"pymatgen": ["db/*.json"]},
    include_package_data=True,
    author="Shyue Ping Ong",
    author_email="shyuep@gmail.com",
    maintainer="Shyue Ping Ong",
    maintainer_email="shyuep@gmail.com",
    url="https://github.com/materialsproject/pymatgen-db",
    license="MIT",
    description="Pymatgen-db is a database add-on for the Python Materials "
    "Genomics (pymatgen) materials analysis library.",
    long_description=long_desc,
    keywords=["vasp", "gaussian", "materials", "project", "electronic", "structure", "mongo"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database",
    ],
    scripts=[
        os.path.join("scripts", f) for f in os.listdir("scripts") if not os.path.isdir(os.path.join("scripts", f))
    ],
)
