
.. codeauthor:: Dan Gunter <dkgunter@lbl.gov>

Materials Project Database Validation: mgvv
============================================

The command-line program, `mgvv`, is used to validate MongoDB databases. This command has two sub-commands:

1. :ref:`mgvv validate <mgvv validate>` - Filter records on a set of criteria (conjunction) and apply a set of constraints.

2. :ref:`mgvv diff <mgvv diff>` - Look at the "diff" of any two collections, for identifiers that are missing from one or the other, or for mis-matching values for identifiers that are the same.

.. _mgvv validate:

.. program:: mgvv

mgvv validate subcommand
-------------------------

Database connections are configured from a file, exactly as for `mgdb`/
The patterns to validate against can come from a file or the command-line.

Arguments
---------

Constraints can be provided on the command line.
The syntax of each constraint is given in :ref:`constraint-syntax`.
It is usually wise to quote the constraints so that the operators are not
interpreted by the Unix shell. The constraints can be listed as separate quoted arguments
or a single quoted argument using commas. For example, the following two command-lines are
equivalent::

        mgvv [options] 'nelements > 1' 'e_above_hull >= 0'
        mgvv [options] 'nelements > 1, e_above_hull >= 0'

The validation constraints could also be configured from a file using the
`--file` option, as described below.

Options
-------

.. option:: --help, -h

show help message and exit

.. option:: --alias, -a

Value is an alias for a field used in a constraint or condition,
in form alias=name_in_db. This option is repeatable to allow multiple
aliases.

.. option:: --collection, -C <name>

Name of collection on which to operate.

.. option:: --email, -e <file or spec>

Email a report.
The sender, server, and recipients can be specified either in a configuration file, or
on the command line in the format "{from}:{to}[:server]".
The "from" and "to" are required; default server is localhost.
If a file path is given (i.e. the option does not have a ':' in it),
then the format is JSON/YAML and the specification should be given
under the "_email" key, which should be a mapping with keys
"from", "to", and "server". For example the following commandline uses localhost:9101 to send mail::

        mgvv [options] --email dkgunter@lbl.gov:somebody@host.org:localhost:9101


See `email-config`_ for an example of the configuration file syntax, which unlike the
command-line syntax allows for multiple recipients.

.. option:: -f <file>, --file <file>

Main configuration file. Has constraints, and optionally email configuration
(see `--email` option).

.. option:: --limit <num>, -m <num>

In output, limit number of displayed validation errors, per collection, to `num`.
The default is 50. To show as many errors as you can find, use 0.

.. option:: --format <type>, -F <type>

Use the specified report type to format and send the validation output.
Recognized types are:

html
    A simple HTML report, with some minimal CSS styling. This is
    arguably the most visually pleasing format. *Default*
json
    A JSON document (indented).
md
    Markdown with an embedded fixed-width table. This is the easiest format
    to read from the console.

.. option:: -c <file>, --config <file>

Configuration file for database connection. Generate one using `mgdb init --config filename.json`, if necessary. Otherwise, the code searches for a db.json.  If none is found, a no-authentication localhost:27017/vasp database is assumed.

.. option:: -v, --verbose

Increase log message verbosity. Repeatable. Messages are logged to standard error.

.. _configuration-files:

Configuration files
-------------------

You can use up to two configuration files: one for constraints (and aliases), one for
the database, and one for the constraints and email.

.. _db-config:

Database configuration
^^^^^^^^^^^^^^^^^^^^^^

The database connection uses the same format as the `mgdb` command for
its :doc:`configuration file <dbconfig>`. The `readonly_user` is preferred over the
administrative user, if both are present.

.. _email-config:

Email configuration
^^^^^^^^^^^^^^^^^^^

Reports can be sent by email. This can be configured on the command-line,
or within the main configuration file.

Here is an example configuration:

.. code-block:: yaml

    _email:
      from: you@host.org
      to:
        - you@host.org
        - othersucker@host.otherorg

The section for email must always be named `_email`.
The purpose of the `_email` key is to make it easy to embed this information into
the configuration file used for the constraints (the `--file` option).
The following keywords are recognized:

from
    Sender email, as a string. Required.
to
    Recipients of the email. If a single one, a string; if multiple, a list of strings. Required.
server
    Email server address. Use 'localhost' if none is given. Optional.
port
    Email server port. Use default SMTP port if none is given. Optional.

.. _constraint-config:

Constraint configuration
^^^^^^^^^^^^^^^^^^^^^^^^

The constraints are configured from a YAML file.

At the top level are keys, which are the names of the collection
on which to apply the constraints. The specification of the constraints in
each collection takes two possible forms, simple and complex. In both cases
the syntax of the constraints is the same, see :ref:`constraint-syntax`.

**Simple**: A list of constraints, which are simply combined. Any document in the collection that violates any of the constraints will generate a validation error.

.. code-block:: yaml

    collection_name:
        - field1 <= value
        - field2 > value
        - # ..etc..

**Complex**: An initial filter, given as a map with an `filter` key, and
a set of constraints under the `constraints` key.
The `filter` key selects records for applying the constraints.
The `constraints` key provides the list of constraints associated with that condition.
As in the simple format, any document in the collection
that violates any of the constraints will generate a validation error.

.. code-block:: yaml

    mycollection:
        -
            filter:
                - field1 = 'negatory'
            constraints:
                - field2 <= value
                - field3 > value
                - # ..etc..
        -
            filter:
                - field1 = 'excellent'
                - field4 > 0
            then:
                - field5 < value
                - # ..etc..

As shown in the second constraint block above, there may also be a 
list of conditions for the `filter`.
All of these conditions must be true for the record
to pass the filter and be evaluated according to the constraints.

**Aliases** can be defined (these operate across all collections, for better or worse, at the moment).
Constraints that use these aliases will automatically be converted to the aliased name before the query
is submitted to the database. The aliases are simply a list in the format "name = value"
in a section called `_aliases`, as shown below.

.. code-block:: yaml

    _aliases:
      - snl_id = mps_id
      - energy = analysis.e_above_hull

**Partial arrays** can be fetched, which is very useful for not spending a ton of bandwidth, by adding `/<path>`
after the name of the field. For example:

.. code-block:: yaml

    collection_name:
        - calculations/density size 2

If, for exampe, the `calculations` array was full of large sub-arrays
this would save a lot of bandwidth by only
retrieving that `density` values for each array item.
By default, the arrays are sliced to only retrieve enough elements
to test against the condition, but this may not be sufficiently efficient for cases where each sub-element is very large.
Note that this only applies to constraints that use the 'size' family of array operators.

.. _constraint-syntax:

Constraint syntax
-----------------

The constraint syntax is taken from the `smoqe package <http://pythonhosted.org/smoqe/>`_.

.. _mgvv diff:

.. program:: mgvv diff

mgvv diff subcommand
---------------------

The `diff` sub-command takes options and two DB configurations::

    mgvv diff [options..] old.json new.json

The command provides a convenient command-line interface to take the difference
of two MongoDB database collections.
Database connections are configured from JSON files, 
exactly as for `mgdb`.
See the :ref:`examples <mgvv diff examples>` at the end of this section for full usage examples.

Arguments
---------

Two positional arguments are required, to set the two collections.
These are called the `old` and `new` collections, respectively. Both
are configured using a pymatgen-db JSON config file.

For an unauthenticated database, we only need 3 keys::

    {
        "host" : "myhost",
        "database": "mydatabase",
        "collection": "mycollection"
    }

For an authenticated database, `user` and `password` (or `readonly_user` and `readonly_password`,
or `admin_user` and `admin_password`) are required::

    {
        "host" : "myhost",
        "database": "mydatabase",
        "collection": "mycollection",
        "user": "me",
        "password": "let-me-in"
    }

Options
-------

usage: mgvv diff [-h] [--verbose] [-D CONFIG] [-E ADDR] [-f FILE] [-F FORMAT] [-s HOST] [-i INFO] [-k KEY] [-m] [-n EXPR] [-p PROPERTIES] [-P] [-q EXPR] [-u URL] [-V] old new

.. option:: --help, -h

show help message and exit

.. option:: -v, --verbose

Increase log message verbosity. Repeatable. Messages are logged to standard error.

.. option:: -D CONFIG, --db CONFIG

Insert a JSON record of the report in the MongoDB collection pointed to by
CONFIG, which is a standard pymatgen-db JSON configuration file. Note that
the target database and collection must be writable.

.. option::  -E ADDR, --email ADDR

Email report to one or more email addresses. ADDR is a list of the form:
'``sender/receiver,[receiver2...][/subject]``'.

.. option:: -s HOST, --email-server HOST

Server HOST for an email report, in form hostname[:port]. Default is localhost

.. option:: -f FILE, --file FILE 

Read options from FILE instead of command line. File format is YAML (or JSON,
a subset), with the long option names as keys. Any time the command-line
option takes a comma-separated list, the config file uses a real list;
command-line key/value pair lists become config file mappings.

For example::

    Command-line                    Config file
    ============                    ==============
    --numeric='x=+-1.5,y=+-0.5'     numeric:
                                       x: '+-1.5'               
                                       y: '+-0.5'

     --info=foo,bar                info:                        
                                       - foo                    
                                       - bar                    

.. option:: -F FORMAT, --format FORMAT

Default report format: 'text', 'html', or 'json'. If not given, the format will be determined by the output: text for console, html for email.

.. option:: -i INFO, --info INFO

Extra fields for records, as comma-separated list, e.g '``extra,fields,to_include``'.

.. option:: -k KEY, --key KEY

Key for matching records.

.. option:: -m, --missing

Only report keys that are in the 'old' collection, but not in the 'new' collection.

.. option:: -n, --numeric

Fields with numeric values that must match, with a tolerance, as a comma-separated list, e.g.,
``<name1>=<expr1>, <name2>=<expr2>, ..``. <name> is a field name, <expr> syntax is:

==========  =======
Expression  Meaning
==========  =======
+-          Change in sign.
+-=         Change in sign, including change from positive or negative to zero.
+-X         Plus or minus more than X. abs(new - old) > X
+X-Y        Plus more than X or minus more than Y. (new - old) > X or (old - new) > Y
+-X=        Plus or minus X or more. abs(new - old) >= X
+X-Y=       Plus X or more, or minus Y or more. (new - old) >= X or (old - new) >= Y
+X[=]       Positive changes only
-Y[=]       Negative changes only
...%        Percent change. Instead of "(new - old)", use "100 * (new - old) / old"
==========  =======

Some examples follow.

* Report records where the value ``analysis.e_above_hull`` changes by more than 20% in either direction::

        mgvv diff -k task_id --numeric "analysis.e_above_hull=+-20%" prod.json dev.json

* Report records where the value ``energy`` changes sign::

        mgvv diff -k name --numeric "energy=+-" conf/test1.json conf/test2.json

* Report records where either the value ``frequency`` or ``duration`` change is some quantity or more::

        mgvv diff -k somekey --numeric "frequency=+1.0-0.5=, duration=+10-15=" foo.json bar.json

This option may be combined with any of the other options.

.. option:: -N, --nanok

Ignore numeric fields where one or both of the values is not a number. This allows the comparison
to continue when, for whatever reason, the new or old value is None.

.. option:: -p PROPS, --properties PROPS

Fields with properties that must match, as comma-separated list , e.g '``these_must,match``'.

.. option:: -P, --print

Print report to the console.

.. option:: -q EXPR, --query EXPR

Query to filter records before key and value tests.
Uses simplified constraint syntax, from the `smoqe package <http://pythonhosted.org/smoqe/>`_. For example::

    --query='name = "oscar" and grouchiness > 3'

.. option::  -u URL, --url URL

In HTML reports, make the key into a hyperlink by prefixing with URL.
This can be used to take advantage of clean RESTful URL schemes such as those found in
the Materials Project webpages::

    mgvv diff -k task_id -u 'https://materialsproject.org/tasks/'

 .. option:: -V, --values

 Only report changes in values, not missing or added keys.

.. _mgvv diff examples:

Examples
--------

Let's say you want to compare the 'materials' collection in a development and production database.
You could have two JSON configuration files, `prod.json` and `dev.json` that specified the servers,
user and password, and database and collection names::

    # prod database
    {
    "host": "server1.my.domain",
    "database": "core_prod",
    "readonly_user": "xxxx",
    "readonly_password": "yyyy",
    "collection": "materials"
    }

    # dev database
    {
    "host": "server2.my.domain",
    "database": "core_dev",
    "readonly_user": "xxxx",
    "readonly_password": "yyyy",
    "collection": "materials"
    }


You could issue this command-line::

    mgvv diff -k task_id  -p icsd_id -v -i pretty_formula mdev.json mprod.json

This compares with the key `task_id` and matches items with the same key on
the property `icsd_id`, adding to the output the value of the field
`pretty_formula`. Because output is to the console, the format will default to
text.

To produce and view an HTML output report instead, just use the `--format` option::

    mgvv diff --format html -k task_id  -p icsd_id -v -i pretty_formula mdev.json mprod.json > page.html
    open page.html # on OSX, view in a browser

To add an email report set the recipient and, optionally, the relay server (default will be localhost)::

    mgvv diff -e "me@my.mail.domain/you@your.mail.domain/DB diff" \
        -k task_id  -p icsd_id -v -i pretty_formula mdev.json mprod.json

Note that the third part of the `-e/--email` command, the subject, is optional -- but if you leave it out the email will arrive with no subject line.

As you may have noticed, the command-lines begin to get rather complicated. To replace that last example with a configuration file, use instead this command::

    mgvv diff --file diff.yaml mdev.json mprod.json

and then put the options into `diff.yaml` like this::

    email:
        - "me@my.mail.domain/you@your.mail.domain/DB diff"
    key: task_id
    properties:
        - icsd_id
    info:
        - pretty_formula
