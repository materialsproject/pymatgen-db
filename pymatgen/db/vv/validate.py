"""
Collection validator
"""
__author__ = "Dan Gunter"
__copyright__ = "Copyright 2012-2013, The Materials Project"
__version__ = "1.0"
__maintainer__ = "Dan Gunter"
__email__ = "dkgunter@lbl.gov"
__status__ = "Development"
__date__ = "1/31/13"

import pymongo
import random
import sys
import collections
import re
from .util import DoesLogging, total_size
from smoqe.query import *


class DBError(Exception):
    pass


class ValidatorSyntaxError(Exception):
    "Syntax error in configuration of Validator"

    def __init__(self, target, desc):
        msg = f'Invalid syntax: {desc} -> "{target}"'
        Exception.__init__(self, msg)


class PythonMethod:
    """Encapsulate an external Python method that will be run on our target
    MongoDB collection to perform arbitrary types of validation.
    """

    _PATTERN = re.compile(r"\s*(@\w+)(\s+\w+)*")

    CANNOT_COMBINE_ERR = "Call to a Python method cannot be combined "
    "with any other constraints"
    BAD_CONSTRAINT_ERR = "Invalid constraint (must be: @<method> [<param> ..])"

    @classmethod
    def constraint_is_method(cls, text):
        """Check from the text of the constraint whether it is
        a Python method, as opposed to a 'normal' constraint.

        :return: True if it is, False if not
        """
        m = cls._PATTERN.match(text)
        return m is not None

    def __init__(self, text):
        """Create new instance from a raw constraint string.

        :raises: ValidatorSyntaxerror
        """
        if not self._PATTERN.match(text):
            raise ValidatorSyntaxError(text, self.BAD_CONSTRAINT_ERR)
        tokens = re.split(r"@?\s+", text)
        if len(tokens) < 1:
            raise ValidatorSyntaxError(text, self.BAD_CONSTRAINT_ERR)
        self.method = tokens[0]
        self.params = tokens[1:]


def mongo_get(rec, key, default=None):
    """
    Get value from dict using MongoDB dot-separated path semantics.
    For example:

    >>> assert mongo_get({'a': {'b': 1}, 'x': 2}, 'a.b') == 1
    >>> assert mongo_get({'a': {'b': 1}, 'x': 2}, 'x') == 2
    >>> assert mongo_get({'a': {'b': 1}, 'x': 2}, 'a.b.c') is None

    :param rec: mongodb document
    :param key: path to mongo value
    :param default: default to return if not found
    :return: value, potentially nested, or default if not found
    :raise: ValueError, if record is not a dict.
    """
    if not rec:
        return default
    if not isinstance(rec, collections.Mapping):
        raise ValueError("input record must act like a dict")
    if not "." in key:
        return rec.get(key, default)
    for key_part in key.split("."):
        if not isinstance(rec, collections.Mapping):
            return default
        if not key_part in rec:
            return default
        rec = rec[key_part]
    return rec


class Projection:
    """Fields on which to project the query results."""

    def __init__(self):
        self._fields = {}
        self._slices = {}

    def add(self, field, op=None, val=None):
        """Update report fields to include new one, if it doesn't already.

        :param field: The field to include
        :type field: Field
        :param op: Operation
        :type op: ConstraintOperator
        :return: None
        """
        if field.has_subfield():
            self._fields[field.full_name] = 1
        else:
            self._fields[field.name] = 1
        if op and op.is_size() and not op.is_variable():
            # get minimal part of array with slicing,
            # but cannot use slice with variables
            self._slices[field.name] = val + 1
        if op and op.is_variable():
            # add the variable too
            self._fields[val] = 1

    def to_mongo(self):
        """Translate projection to MongoDB query form.

        :return: Dictionary to put into a MongoDB JSON query
        :rtype: dict
        """
        d = copy.copy(self._fields)
        for k, v in self._slices.items():
            d[k] = {"$slice": v}
        return d


class ConstraintViolation:
    """A single constraint violation, with no metadata."""

    def __init__(self, constraint, value, expected):
        """Create new constraint violation

        :param constraint: The constraint that was violated
        :type constraint: Constraint
        """
        self._constraint = constraint
        self._got = value
        self._expected = expected

    @property
    def field(self):
        return self._constraint.field.name

    @property
    def op(self):
        # return str(self._constraint.op)
        return self._constraint.op.display_op

    @property
    def got_value(self):
        return self._got

    @property
    def expected_value(self):
        return self._expected

    @expected_value.setter
    def expected_value(self, value):
        self._expected = value


class NullConstraintViolation(ConstraintViolation):
    """Empty constraint violation, for when there are no constraints."""

    def __init__(self):
        ConstraintViolation.__init__(self, Constraint("NA", "=", "NA"), "NA", "NA")


class ConstraintViolationGroup:
    """A group of constraint violations with metadata."""

    def __init__(self):
        """Create an empty object."""
        self._viol = []
        # These are read/write
        self.subject = ""
        self.condition = None

    def add_violations(self, violations, record=None):
        """Add constraint violations and associated record.

        :param violations: List of violations
        :type violations: list(ConstraintViolation)
        :param record: Associated record
        :type record: dict
        :rtype: None
        """
        rec = {} if record is None else record
        for v in violations:
            self._viol.append((v, rec))

    def __iter__(self):
        return iter(self._viol)

    def __len__(self):
        return len(self._viol)


class ProgressMeter:
    """Simple progress tracker"""

    def __init__(self, num, fmt):
        self._n = num
        self._subject = "?"
        self._fmt = fmt
        self._count = 0
        self._total = 0

    @property
    def count(self):
        return self._total

    def set_subject(self, subj):
        self._subject = subj

    def update(self, *args):
        self._count += 1
        self._total += 1
        if self._n == 0 or self._count < self._n:
            return
        sys.stderr.write(self._fmt.format(*args, subject=self._subject, count=self.count))
        sys.stderr.write("\n")
        sys.stderr.flush()
        self._count = 0


class ConstraintSpec(DoesLogging):
    """Specification of a set of constraints for a collection."""

    FILTER_SECT = "filter"
    CONSTRAINT_SECT = "constraints"
    SAMPLE_SECT = "sample"

    def __init__(self, spec):
        """Create specification from a configuration.

        :param spec: Configuration for a single collection
        :type spec: dict
        :raise: ValueError if specification is wrong
        """
        DoesLogging.__init__(self, name="mg.ConstraintSpec")
        self._sections, _slist = {}, []
        for item in spec:
            self._log.debug(f"build constraint from: {item}")
            if isinstance(item, dict):
                self._add_complex_section(item)
            else:
                self._add_simple_section(item)

    def __iter__(self):
        """Return a list of all the sections.

        :rtype: list(ConstraintSpecSection)
        """
        sect = []
        # simple 1-level flatten operation
        for values in self._sections.values():
            for v in values:
                sect.append(v)
        return iter(sect)

    def _add_complex_section(self, item):
        """Add a section that has a filter and set of constraints

        :raise: ValueError if filter or constraints is missing
        """
        # extract filter and constraints
        try:
            fltr = item[self.FILTER_SECT]
        except KeyError:
            raise ValueError(f"configuration requires '{self.FILTER_SECT}'")
        sample = item.get(self.SAMPLE_SECT, None)
        constraints = item.get(self.CONSTRAINT_SECT, None)

        section = ConstraintSpecSection(fltr, constraints, sample)
        key = section.get_key()
        if key in self._sections:
            self._sections[key].append(section)
        else:
            self._sections[key] = [section]

    def _add_simple_section(self, item):
        self._sections[None] = [ConstraintSpecSection(None, item, None)]


class ConstraintSpecSection:
    def __init__(self, fltr, constraints, sample):
        self._filter, self._constraints, self._sampler = fltr, constraints, sample
        # make condition(s) into a tuple
        if isinstance(fltr, basestring):
            self._key = (fltr,)
        elif fltr is None:
            self._key = None
        else:
            self._key = tuple(fltr)
        # parse sample keywords into class, if present
        if sample:
            self._sampler = Sampler(**sample)

    def get_key(self):
        return self._key

    @property
    def sampler(self):
        return self._sampler

    @property
    def filters(self):
        return self._filter

    @property
    def constraints(self):
        return self._constraints


class Validator(DoesLogging):
    """Validate a collection."""

    class SectionParts:
        """Encapsulate the tuple of information for each section of filters, constraints,
        etc. within a collection.
        """

        def __init__(self, cond, body, sampler, report_fields):
            """Create new initialized set of parts.

            :param cond: Condition to filter records
            :type cond: MongoQuery
            :param body: Main set of constraints
            :type body: MongoQuery
            :param sampler: Sampling class if any
            :type sampler: Sampler
            :param report_fields: Fields to report on
            :type report_fields: list
            """
            self.cond, self.body, self.sampler, self.report_fields = (
                cond,
                body,
                sampler,
                report_fields,
            )

    def __init__(self, max_violations=50, max_dberrors=10, aliases=None, add_exists=False):
        DoesLogging.__init__(self, name="mg.validator")
        self.set_progress(0)
        self._aliases = aliases if aliases else {}
        self._max_viol = max_violations
        if self._max_viol > 0:
            self._find_kw = {"limit": self._max_viol}
        else:
            self._find_kw = {}
        self._max_dberr = max_dberrors
        self._base_report_fields = {"_id": 1, "task_id": 1}
        self._add_exists = add_exists

    def set_progress(self, num):
        """Report progress every `num` bad records.

        :param num: Report interval
        :type num: int
        :return: None
        """
        report_str = "Progress for {subject}: {count:d} invalid, {:d} db errors, {:d} bytes"
        self._progress = ProgressMeter(num, report_str)

    def num_violations(self):
        if self._progress is None:
            return 0
        return self._progress._count

    def validate(self, coll, constraint_spec, subject="collection"):
        """Validation of  a collection.
        This is a generator that yields ConstraintViolationGroups.

        :param coll: Mongo collection
        :type coll: pymongo.Collection
        :param constraint_spec: Constraint specification
        :type constraint_spec: ConstraintSpec
        :param subject: Name of the thing being validated
        :type subject: str
        :return: Sets of constraint violation, one for each constraint_section
        :rtype: ConstraintViolationGroup
        :raises: ValidatorSyntaxError
        """
        self._spec = constraint_spec
        self._progress.set_subject(subject)
        self._build(constraint_spec)
        for sect_parts in self._sections:
            cvg = self._validate_section(subject, coll, sect_parts)
            if cvg is not None:
                yield cvg

    def _validate_section(self, subject, coll, parts):
        """Validate one section of a spec.

        :param subject: Name of subject
        :type subject: str
        :param coll: The collection to validate
        :type coll: pymongo.Collection
        :param parts: Section parts
        :type parts: Validator.SectionParts
        :return: Group of constraint violations, if any, otherwise None
        :rtype: ConstraintViolationGroup or None
        """
        cvgroup = ConstraintViolationGroup()
        cvgroup.subject = subject

        # If the constraint is an 'import' of code, treat it differently here
        # if self._is_python(parts):
        #    num_found = self._run_python(cvgroup, coll, parts)
        #    return None if num_found == 0 else cvgroup

        query = parts.cond.to_mongo(disjunction=False)
        query.update(parts.body.to_mongo())
        cvgroup.condition = parts.cond.to_mongo(disjunction=False)
        self._log.debug(f"Query spec: {query}")
        self._log.debug(f"Query fields: {parts.report_fields}")
        # Find records that violate 1 or more constraints
        cursor = coll.find(query, parts.report_fields, **self._find_kw)
        if parts.sampler is not None:
            cursor = parts.sampler.sample(cursor)
        nbytes, num_dberr, num_rec = 0, 0, 0
        while 1:
            try:
                record = next(cursor)
                nbytes += total_size(record)
                num_rec += 1
            except StopIteration:
                self._log.info(
                    "collection {}: {:d} records, {:d} bytes, {:d} db-errors".format(
                        subject, num_rec, nbytes, num_dberr
                    )
                )
                break
            except pymongo.errors.PyMongoError as err:
                num_dberr += 1
                if num_dberr > self._max_dberr > 0:
                    raise DBError("Too many errors")
                self._log.warn(f"DB.{num_dberr:d}: {err}")
                continue

            # report progress
            if self._progress:
                self._progress.update(num_dberr, nbytes)
            # get reasons for badness
            violations = self._get_violations(parts.body, record)
            cvgroup.add_violations(violations, record)
        return None if nbytes == 0 else cvgroup

    def _get_violations(self, query, record):
        """Reverse-engineer the query to figure out why a record was selected.

        :param query: MongoDB query
        :type query: MongQuery
        :param record: Record in question
        :type record: dict
        :return: Reasons why bad
        :rtype: list(ConstraintViolation)
        """
        # special case, when no constraints are given
        if len(query.all_clauses) == 0:
            return [NullConstraintViolation()]
        # normal case, check all the constraints
        reasons = []
        for clause in query.all_clauses:
            var_name = None
            key = clause.constraint.field.name
            op = clause.constraint.op
            fval = mongo_get(record, key)
            if fval is None:
                expected = clause.constraint.value
                reasons.append(ConstraintViolation(clause.constraint, "missing", expected))
                continue
            if op.is_variable():
                # retrieve value for variable
                var_name = clause.constraint.value
                value = mongo_get(record, var_name, default=None)
                if value is None:
                    reasons.append(ConstraintViolation(clause.constraint, "missing", var_name))
                    continue
                clause.constraint.value = value  # swap out value, temporarily
            # take length for size
            if op.is_size():
                if isinstance(fval, str) or not hasattr(fval, "__len__"):
                    reasons.append(ConstraintViolation(clause.constraint, type(fval), "sequence"))
                    if op.is_variable():
                        clause.constraint.value = var_name  # put original value back
                    continue
                fval = len(fval)
            ok, expected = clause.constraint.passes(fval)
            if not ok:
                reasons.append(ConstraintViolation(clause.constraint, fval, expected))
            if op.is_variable():
                clause.constraint.value = var_name  # put original value back
        return reasons

    def _build(self, constraint_spec):
        """Generate queries to execute.

        Sets instance variables so that Mongo query strings, etc. can now
        be extracted from the object.

        :param constraint_spec: Constraint specification
        :type constraint_spec: ConstraintSpec
        """
        self._sections = []

        # For each condition in the spec

        for sval in constraint_spec:
            rpt_fld = self._base_report_fields.copy()
            # print("@@ CONDS = {}".format(sval.filters))
            # print("@@ MAIN = {}".format(sval.constraints))

            # Constraints

            # If the constraint is an external call to Python code
            if self._is_python(sval.constraints):
                query, proj = self._process_python(sval.constraints)
                rpt_fld.update(proj.to_mongo())

            # All other constraints, e.g. 'foo > 12'
            else:
                query = MongoQuery()
                if sval.constraints is not None:
                    groups = self._process_constraint_expressions(sval.constraints)
                    projection = Projection()
                    for cg in groups.values():
                        for c in cg:
                            projection.add(c.field, c.op, c.value)
                            query.add_clause(MongoClause(c))
                        if self._add_exists:
                            for c in cg.existence_constraints:
                                query.add_clause(MongoClause(c, exists_main=True))
                    rpt_fld.update(projection.to_mongo())

            # Filters

            cond_query = MongoQuery()
            if sval.filters is not None:
                cond_groups = self._process_constraint_expressions(sval.filters, rev=False)
                for cg in cond_groups.values():
                    for c in cg:
                        cond_query.add_clause(MongoClause(c, rev=False))

            # Done. Add a new 'SectionPart' for the filter and constraint

            result = self.SectionParts(cond_query, query, sval.sampler, rpt_fld)
            self._sections.append(result)

    def _process_constraint_expressions(self, expr_list, conflict_check=True, rev=True):
        """Create and return constraints from expressions in expr_list.

        :param expr_list: The expressions
        :conflict_check: If True, check for conflicting expressions within each field
        :return: Constraints grouped by field (the key is the field name)
        :rtype: dict
        """
        # process expressions, grouping by field
        groups = {}
        for expr in expr_list:
            field, raw_op, val = parse_expr(expr)
            op = ConstraintOperator(raw_op)
            if field not in groups:
                groups[field] = ConstraintGroup(Field(field, self._aliases))
            groups[field].add_constraint(op, val)

        # add existence constraints
        for cgroup in groups.values():
            cgroup.add_existence(rev)

        # optionally check for conflicts
        if conflict_check:
            # check for conflicts in each group
            for field_name, group in groups.items():
                conflicts = group.get_conflicts()
                if conflicts:
                    raise ValueError(f"Conflicts for field {field_name}: {conflicts}")
        return groups

    def _is_python(self, constraint_list):
        """Check whether constraint is an import of Python code.

        :param constraint_list: List of raw constraints from YAML file
        :type constraint_list: list(str)
        :return: True if this refers to an import of code, False otherwise
        :raises: ValidatorSyntaxError
        """
        if len(constraint_list) == 1 and PythonMethod.constraint_is_method(constraint_list[0]):
            return True
        if len(constraint_list) > 1 and any(filter(PythonMethod.constraint_is_method, constraint_list)):
            condensed_list = "/".join(constraint_list)
            err = PythonMethod.CANNOT_COMBINE_ERR
            raise ValidatorSyntaxError(condensed_list, err)
        return False

    def _process_python(self, expr_list):
        """Create a wrapper for a call to some external Python code.

        :param expr_list: The expressions
        :return: Tuple of (query, field-projection)
        :rtype: (PythonMethod, Projection)
        """
        return None, None

    def set_aliases(self, new_value):
        "Set aliases and wrap errors in ValueError"
        try:
            self.aliases = new_value
        except Exception as err:
            raise ValueError(f"invalid value: {err}")


class Sampler(DoesLogging):
    """Randomly sample a proportion of the full collection."""

    # Random uniform distribution
    DIST_RUNIF = 1
    # Default distribution
    DEFAULT_DIST = DIST_RUNIF
    # Names of distributions
    DIST_CODES = {"uniform": DIST_RUNIF}

    def __init__(self, min_items=0, max_items=1e9, p=1.0, distrib=DEFAULT_DIST, **kw):
        """Create new parameterized sampler.

        :param min_items: Minimum number of items in the sample
        :param max_items: Maximum number of items in the sample
        :param p: Probability of selecting an item
        :param distrib: Probability distribution code, one of DIST_<name> in this class
        :type distrib: str or int
        :raise: ValueError, if `distrib` is an unknown code or string
        """
        DoesLogging.__init__(self, "mg.sampler")
        # Sanity checks
        if min_items < 0:
            raise ValueError(f"min_items cannot be negative ({min_items:d})")
        if (max_items != 0) and (max_items < min_items):
            raise ValueError(f"max_items must be zero or >= min_items ({max_items:d} < {min_items:d})")
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"probability, p, must be between 0 and 1 ({p:f})")
        self.min_items = min_items
        self.max_items = max_items
        self.p = p
        self._empty = True
        # Distribution
        if not isinstance(distrib, int):
            distrib = self.DIST_CODES.get(str(distrib), None)
        if distrib == self.DIST_RUNIF:
            self._keep = self._keep_runif
        else:
            raise ValueError(f"unrecognized distribution: {distrib}")

    @property
    def is_empty(self):
        return self._empty

    def _keep_runif(self):
        return self.p >= random.uniform(0, 1)

    def sample(self, cursor):
        """Extract records randomly from the database.
        Continue until the target proportion of the items have been
        extracted, or until `min_items` if this is larger.
        If `max_items` is non-negative, do not extract more than these.

        This function is a generator, yielding items incrementally.

        :param cursor: Cursor to sample
        :type cursor: pymongo.cursor.Cursor
        :return: yields each item
        :rtype: dict
        :raise: ValueError, if max_items is valid and less than `min_items`
                or if target collection is empty
        """
        count = cursor.count()

        # special case: empty collection
        if count == 0:
            self._empty = True
            raise ValueError("Empty collection")

        # special case: entire collection
        if self.p >= 1 and self.max_items <= 0:
            for item in cursor:
                yield item
            return

        # calculate target number of items to select
        if self.max_items <= 0:
            n_target = max(self.min_items, self.p * count)
        else:
            if self.p <= 0:
                n_target = max(self.min_items, self.max_items)
            else:
                n_target = max(self.min_items, min(self.max_items, self.p * count))
        if n_target == 0:
            raise ValueError("No items requested")

        # select first `n_target` items that pop up with
        # probability self.p
        # This is actually biased to items at the beginning
        # of the file if n_target is smaller than (p * count),
        n = 0
        while n < n_target:
            try:
                item = next(cursor)
            except StopIteration:
                # need to keep looping through data until
                # we get all our items!
                cursor.rewind()
                item = next(cursor)
            if self._keep():
                yield item
                n += 1
