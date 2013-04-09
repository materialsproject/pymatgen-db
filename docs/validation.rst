
.. codeauthor:: Dan Gunter <dkgunter@lbl.gov>

****************
Validation tools
****************

There are four modules to validation, which will be applied in this order to a given collection:

#.  Filter records on a set of criteria (conjunction)
#.  Apply simple constraints and find records that do not match any given constraint (disjunction)
#.  Sub-sample results of 1. and 2. (which may be empty, i.e. the whole collection)
#.  Apply arbitrary Python functions to the entire result-set of 1 through 3, each function getting its own virtual copy of the result set and optionally other parameters allowing, e.g., queries to other collections in the database.

*Status*: Numbers 1 and 2 above are complete. Number 3 is nearly complete, for number 4 there are a couple of existing
functions but they need to be integrated into this framework.

All of these modules can be invoked through APIs, eventually, but the current primary interface is the
command-line program, `mgvv`_. The rest of this page describes the usage of this program.


mgvv
====

.. program:: mgvv

The `mgvv` program provides a convenient command-line interface to run
validation tests of MongoDB databases.
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
 "from", "to", and "server".
For example the following commandline uses localhost:9101 to send mail::

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

constraint syntax
-----------------

The general syntax of a constraint is three whitespace-separated tokens: `field.name operator value`.

field.name
    This is a path to the field in a document, using the MongoDB convention of using the "." character
    to indicate hierarchy. For example, in the following document the field containing the names of
    some famous jazz saxophonists would be named `musicians.jazz.sax`::

        { 'musicians' :
            { 'jazz' :
                { 'sax' :
                   [ "John Coltrane", "Charlie Parker", "Coleman Hawkins" ]
                }
            }
        }

operator
    The following operators are supported:

    - `<`, `<=`, `>`, `>=`, `=`, `!=`: Constrain numeric values, with their usual meanings. The '=' and '!=' operators can also test the value of string or boolean values.
    - `exists`: Is the field present (true) or not present (false) in the document
    - `size`: Match the size (integer) of the array. This operator also takes a one-character suffix:
        - `size<`: size is less than the (integer) value
        - `size>`: size is greater than the (integer) value
        - `size$`: size is equal to the value of the variable named by the (string) value
    - `type`: the datatype of the field must match the given value, which can be either "number" or "string".

value
    The value can be numeric (integer or floating-point), a string, an identifier, or boolean value.
    An identifier is a restricted class of string that starts with a letter, has no spaces, and has only
    letters, digits, underscores and dots. All other strings must be quoted with single or double quotes.
    Boolean values are either `true` or `false` (case-insensitive, so TRUE would
    also work).

Below are some example constraints::

    weight < 200
    prefs.color = 'puce'
    prefs.food.dessert exists true       # must be present
    prefs.food.salted_fish exists false  # must not be present
    my.array size 0                      # array is present, but empty
    your.array size> 1                   # array must have more than one element
    their.array size$ foo.bar            # array size must be the same as value of foo.bar element
    weight type number                   # weight must be a number
    prefs.food.dessert type string       # must be a string
