# Database builders

Author: Dan Gunter <dkgunter@lbl.gov>
Modified: 2014-04-23

Code to build and merge MongoDB databases.

## About

This codebase uses a "plugin" type of architecture, where directories of python modules,
inheriting from classes in core.py,  can be discovered and used at runtime to build new
databases.

* core.py - Run builders against the DB
* schema.py - Parse and validate schema definitions
* incr.py - Incremental building
* util.py - Functions that don't fall clearly in any of the modules above

The "plugins" should be Python packages with subdirectories that
follow this convention:

* Put "builder" modules at the top-level in a file names {something}_builder.py
* Schemata for collections are in schemas/{collection}_schema.json

## Optional additional conventions

* Tests, as usual, go in a tests/ directory
* Additional notes should go in a Readme.md at the top-level
