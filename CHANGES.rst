v0.7.0
------
* Fix deprecation.
* Ensure oxide types are handled properly in creating docs and querying for
  them.

v0.6.2
------
* Minor bug fixes.

v0.6.1
------
* Removed Materials Genomics UI. Pls use Flamyngo as an alternative.

v0.6.5
------
1. Proper specification of requirements.

v0.6.2
------
1. Update dependency versions.

v0.5.0
------
* Updated scripts for new MongoClient.

v0.4.8
------
* Update pymatgen vand other dependencies.

v0.4.1
------

#. Refactor of builders (mgbuild and matgendb.builders) to
   improve usability. Github issues #9 through #13.
#. Also for 'builders', added incremental building
#. Added modules dbgroup and dbconfig for more flexible and powerful
   configuration of multiple databases with a directory of configuration files.

v0.4.0
------
New `mgvv diff` features.

#. Configure from YAML file
#. Improved JSON output
#. Add JSON reports to a database
#. Sort numeric diffs by delta value

v0.3.9
------
#. `mgvv diff` HTML output can make they key field into a hyperlink using a user-provided prefix
#. Added brief introduction to `mgvv` in front page of Sphinx docs

v0.3.8
------
#. `mgvv diff` can perform numeric diffs. Better error handling.

v0.3.7
------
#. New package maintainer, Dan Gunter <dkgunter@lbl.gov>
#. Added `vv.diff` package and associated `mgvv diff` subcommand, for taking the difference of two arbitrary MongoDB collections.
#. Some cleanup and simplification of config files. `user` and `password` are accepted as aliases for `readonly_user` and `readonly_password`.


v0.3.4
------
1. MAPI_KEY is now a db config file variable.

v0.3.3
------
1. Minor bug fix release.

v0.3.2
------
1. Add option to use the Materials API to obtain stability data during run
   insertion.
2. Materials Genomics UI now supports setting a limit on number of results
   returned.
3. Improvements to mgdb script to allow setting of hosts, etc.

v0.3.0
------
1. Significant update to materials genomics ui. Ability to export table data
   to CSV, XLS or PDF.
2. First vof RESTful interface implemented.
