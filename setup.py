import os

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages

with open("README.rst") as f:
    long_desc = f.read()
    #ind = long_desc.find("\n")
    #long_desc = long_desc[ind + 1:]

static_data = []
for parent, dirs, files in os.walk(os.path.join("matgendb", "webui",
                                                "static")):
    for f in files:
        if not f.endswith(".psd"):
            static_data.append(os.path.join(parent.lstrip("matgendb/webui/"),
                                            f))

setup(
    name="pymatgen-db",
    packages=find_packages(),
    version="0.3.0",
    install_requires=["pymatgen>=2.5", "pymongo>=2.4", "prettytable>=0.7",
                      "django>=1.5"],
    package_data={"matgendb": ["*.json"],
                  "matgendb.webui.home": ["templates/*"],
                  "matgendb.webui": static_data},
    author="Shyue Ping Ong",
    author_email="shyuep@gmail.com",
    maintainer="Shyue Ping Ong",
    url="https://github.com/materialsproject/pymatgen-db",
    license="MIT",
    description="Pymatgen-db is a database add-on for the Python Materials "
                "Genomics (pymatgen) materials analysis library.",
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
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database",
        "Topic :: Database :: Front-Ends"
    ],
    download_url="https://github.com/materialsproject/pymatgen-db/tarball/master",
    scripts=[os.path.join("scripts", f) for f in os.listdir("scripts")]
)
