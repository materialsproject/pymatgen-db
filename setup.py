import os

from distribute_setup import use_setuptools
use_setuptools(version='0.6.10')
from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()
    ind = long_desc.find("\n")
    long_desc = long_desc[ind + 1:]

setup(
    name="pymatgen-db",
    packages=find_packages(),
    version="0.1.2dev",
    install_requires=["pymatgen>=2.5", "pymongo>=2.4", "prettytable>=0.7"],
    package_data={"matgendb": ["*.json"]},
    author="Shyue Ping Ong",
    author_email="shyuep@gmail.com",
    maintainer="Shyue Ping Ong",
    url="https://github.com/materialsproject/pymatgen-db",
    license="MIT",
    description="pymatgen is the Python materials analysis library powering "
                "the Materials Project (www.materialsproject.org).",
    long_description=long_desc,
    keywords=["vasp", "gaussian", "materials", "project", "electronic",
              "structure", "mongo"],
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    download_url="https://github.com/materialsproject/pymatgen-db/tarball/master",
    scripts=[os.path.join("scripts", f) for f in os.listdir("scripts")]
)
