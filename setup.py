# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os

from setuptools import setup, find_namespace_packages

with open("README.rst") as f:
    long_desc = f.read()

setup(
    name="pymatgen-db",
    packages=find_namespace_packages(include=["pymatgen.*"]),
    version="2022.3.17",
    setup_requires=["numpy"],
    install_requires=["pymatgen>=2022.0.3", "monty>=0.9.6", "pymongo>=2.8", "smoqe"],
    extras_require={
        'tests': 'mongomock'
    },
    package_data={"pymatgen": ["db/*.json"]},
    include_package_data=True,
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
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
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