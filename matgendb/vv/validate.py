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

import copy
import math
import pymongo
import random
import re
import sys
from numbers import Number

from .util import DoesLogging, total_size


class DBError(Exception):
    pass


def mongo_get(rec, key, default=None):
    """Get value from dict using MongoDB dot-separated path semantics.

    For example:
        get_mongo({'a':{'b':1}, x:2}, 'a.b') -> 1
        get_mongo({'a':{'b':1}, x:2}, 'x') -> 2
        get_mongo({'a':{'b':1}, x:2}, 'a.b.c') -> None

    :param rec: mongodb document
    :param key: path to mongo value
    :param default: default to return if not found
    :return: value, potentially nested, or default if not found
    :raise: ValueError, if record is not a dict or key is invalid.
    """
    if not rec:
        return default
    if not hasattr(rec, 'get'):
        raise ValueError('input record must act like a dict')
    if not '.' in key:
        return rec.get(key, default)
    for key_part in key.split('.'):
        if not key_part in rec:
            return default
        rec = rec[key_part]
    return rec


class Field:
    """Single field in a constraint.
    """

    PICK_SEP = '/'   # embedded syntax for picking subfield

    def __init__(self, name, aliases=None):
        """Create from field name.

        :param name: Field name.
        :type name: str
        :param aliases: Aliases for all fields
        :type aliases: dict
        :raise: ValueError for non-string name
        """
        if not isinstance(name, str):
            raise ValueError('Field name must be a string')
        if aliases is not None:
            name = aliases.get(name, name)
        # assign field name and possible subfield name
        if self.PICK_SEP in name:
            self._name, self._subname = name.split(self.PICK_SEP)
        else:
            self._name, self._subname = name, None

    def has_subfield(self):
        return self._subname is not None

    @property
    def name(self):
        return self._name

    @property
    def full_name(self, sep='.'):
        return sep.join((self._name, self._subname))

    @property
    def sub_name(self):
        return self._subname


class ConstraintOperator:
    """Operator in a single constraint.
    """
    SIZE = 'size'
    EXISTS = 'exists'
    TYPE = 'type'

    # enumeration of size operation modifiers
    SZ_EQ, SZ_GT, SZ_LT, SZ_VAR = 1, 2, 3, 4
    SZ_MAPPING = {'>': SZ_GT, '<': SZ_LT, '$': SZ_VAR}
    SZ_OPS = {SZ_GT: '>', SZ_LT: '<', SZ_EQ: '=', SZ_VAR: '='}

    # logical 'not' of an operator
    OP_NOT = {'>': '<=', '>=': '<', '<': '>=', '<=': '>', '=': '!=', '!=': '=',
              EXISTS: EXISTS, SIZE: SIZE, TYPE: TYPE}

    # set of valid operations
    VALID_OPS = set(OP_NOT.keys())
    for size_sfx in SZ_MAPPING:
        VALID_OPS.add(SIZE + size_sfx)

    # mapping to python operators, where different, for inequalities
    PY_INEQ = {'=': '=='}

    def __init__(self, op):
        """Create new operator.

        :param op: Operator string
        :type op: str
        :raise: ValueError for bad op
        """
        if not isinstance(op, str) or not op in self.VALID_OPS:
            raise ValueError('bad operation: {}'.format(op))
        self._op = op
        self._set_size_code()
        if self.is_size():
            # strip down to prefix
            self._op = self.SIZE

    def __str__(self):
        return self._op

    def is_exists(self):
        """Get whether this is an existence operator.
        :return: True or False
        """
        return self._op == self.EXISTS

    @property
    def size_op(self):
        self._check_size()
        return self.SZ_OPS[self._size_code]

    def is_eq(self):
        """Is this an equality operation.

        :return: Whether it is equal
        :rtype: bool
        """
        return self._op == '='

    def is_neq(self):
        return self._op == '!='

    def is_equality(self):
        return self._op in ('=', '!=')

    def is_inequality(self):
        return self._op in ('>', '>=', '<', '<=')

    def is_size(self):
        """Get whether this is a size operator.
        :return: True or False
        """
        return self._size_code is not None

    def is_variable(self):
        """Whether the operator target is a variable

        :return: True or False
        """
        return self._size_code == self.SZ_VAR

    def is_size_lt(self):
        """Is this a less-than size operator.

        :return: True or False
        :rtype: bool
        :raise: ValueError, if not a size operator at all
        """
        self._check_size()
        return self._size_code == self.SZ_LT

    def is_size_eq(self):
        """Is this an equality size operator.

        :return: True or False
        :rtype: bool
        :raise: ValueError, if not a size operator at all
        """
        self._check_size()
        return self._size_code == self.SZ_EQ

    def is_size_gt(self):
        """Is this a greater-than size operator.

        :return: True or False
        :rtype: bool
        :raise: ValueError, if not a size operator at all
        """
        self._check_size()
        return self._size_code == self.SZ_GT

    def is_type(self):
        """Whether the operator is 'type'

        :return: True or False
        """
        return self._op == self.TYPE

    def reverse(self):
        self._op = self.OP_NOT[self._op]

    def _check_size(self):
        if self._size_code is None:
            raise RuntimeError('Attempted to fetch size code for non-size operator')

    def _set_size_code(self):
        """Set the code for a size operation.
        """
        if not self._op.startswith(self.SIZE):
            self._size_code = None
            return

        if len(self._op) == len(self.SIZE):
            self._size_code = self.SZ_EQ
        else:
            suffix = self._op[len(self.SIZE):]
            self._size_code = self.SZ_MAPPING.get(suffix, None)
            if self._size_code is None:
                raise ValueError('invalid "{}" suffix "{}"'.format(self.SIZE, suffix))

    def compare(self, lhs_value, rhs_value):
        """Compare left- and right-size of: value <op> value.

        :param lhs_value: Value to left of operator
        :param rhs_value: Value to right of operator
        :return: True if the comparison is valid
        :rtype: bool
        """
        if self.is_eq():
            # simple {field:value}
            return lhs_value is not None and lhs_value == rhs_value
        if self.is_neq():
            return lhs_value is not None and lhs_value != rhs_value  # XXX: 'or'?
        if self.is_exists():
            if rhs_value:
                return lhs_value is not None
            else:
                return lhs_value is None
        if self.is_size():
            if self.is_size_eq():
                return lhs_value == rhs_value
            if self.is_size_gt():
                return lhs_value > rhs_value
            if self.is_size_lt():
                return lhs_value < rhs_value
            raise RuntimeError('unexpected size operator: {}'.format(self._op))
        if self.is_inequality():
            if not isinstance(lhs_value, Number):
                return False
            py_op = self.PY_INEQ.get(self._op, self._op)
            return eval('{} {} {}'.format(lhs_value, py_op, rhs_value))
        if self.is_type():
            ltype = type(lhs_value)
            if rhs_value is Number:
                return ltype in (int, float)
            elif rhs_value is str:
                return ltype is str
            elif rhs_value is bool:
                return ltype is bool
            return False


class Constraint:
    """Definition of a single constraint.
    """

    # Convert name of type into Python class
    TYPE_MAPPING = {'number': Number, 'int': Number, 'integer': Number, 'float': Number,
                    'str': str, 'string': str, 'bool': bool, 'boolean': bool}

    def __init__(self, field, operator, value):
        """Create constraint on a field.

        :param field: A constraint field
        :type field: Field or str
        :param operator: A constraint operator
        :type operator: ConstraintOperator or str
        :param value: Target value
        :type value: str, Number
        :raise: ValueError if operator/value combination is illegal, or if
                building a Field or ConstraintOperator instance fails.
        """
        if not isinstance(operator, ConstraintOperator):
            operator = ConstraintOperator(operator)
        if not isinstance(field, Field):
            field = Field(field)
        self.field = field
        self._op = operator
        if self._op.is_inequality() and not isinstance(value, Number):
            raise ValueError('inequality with non-numeric value: {}'.format(value))
        elif self._op.is_type():
            value = value.lower()
            t = self.TYPE_MAPPING.get(value, None)
            if t is None:
                allowed = ', '.join(self.TYPE_MAPPING.keys())
                raise ValueError('value for type, {}, not in ({})'.format(value, allowed))
            self._orig_value, value = value, t
        self.value = value

    def passes(self, value):
        """Does the given value pass this constraint?

        :return: True,None if so; False,<expected> if not
        :rtype: tuple
        """
        try:
            if self._op.compare(value, self.value):
                return True, None
            else:
                return False, self.value
        except ValueError, err:
            return False, str(err)

    @property
    def op(self):
        """Constraint operator
        :return: The operator
        :rtype: ConstraintOperator
        """
        return self._op

    def __str__(self):
        return '{} {}'.format(self.field.name, self._op)


class ConstraintGroup:
    """Definition of a group of constraints, for a given field.
    """
    def __init__(self, field=None):
        """

        :param field: The field to which all constraints apply
        :type field: Field (cannot be None)
        """
        assert(field is not None)
        self.constraints = []
        self._existence_constraints = []
        self._array, self._range = False, False
        self._field = field

    def add_constraint(self, op, val):
        """Add new constraint.

        :param op: Constraint operator
        :type op: ConstraintOperator
        :param val: Constraint value
        :type val: str,Number
        :raise: ValueError if combination of constraints is illegal
        """
        if len(self.constraints) > 0:
            if op.is_equality():
                clist = ', '.join(map(str, self.constraints))
                raise ValueError('Field {}: equality operator cannot be combined '
                                 'with others: {}'.format(self._field.name, clist))
            elif op.is_exists():
                raise ValueError('Field {}: existence is implied '
                                 'by other operators'.format(self._field.name))
        constraint = Constraint(self._field, op, val)
        self.constraints.append(constraint)
        if self._field.has_subfield():
            self._array = True
        elif op.is_inequality():
            self._range = True

    def has_array(self):
        return self._array

    def get_conflicts(self):
        """Get conflicts in constraints, if any.

        :return: Description of each conflict, empty if none.
        :rtype: list(str)
        """
        conflicts = []
        if self._array and self._range:
            conflicts.append('cannot use range expressions on arrays')
        return conflicts

    def add_existence(self, rev):
        """Add existence constraint for the field.

        This is necessary because the normal meaning of 'x > 0' is: x > 0 and is present.
        Without the existence constraint, MongoDB will treat 'x > 0' as: 'x' > 0 *or* is absent.
        Of course, if the constraint is already about existence, nothing is done.

        :rtype: None
        """
        if len(self.constraints) == 1 and (
                # both 'exists' and strict equality don't require the extra clause
                self.constraints[0].op.is_exists() or
                self.constraints[0].op.is_equality()):
            return
        value = not rev   # value is False if reversed, otherwise True
        constraint = Constraint(self._field, ConstraintOperator.EXISTS, value)
        self._existence_constraints.append(constraint)

    @property
    def existence_constraints(self):
        return self._existence_constraints

    def __iter__(self):
        return iter(self.constraints)


class MongoClause:
    """Representation of query clause in a MongoDB query.
       Ho, Ho, Ho! Merry Mongxmas!
    """
    # Target location, main part of query or where-clauses
    LOC_MAIN, LOC_WHERE, LOC_MAIN2 = 0, 1, 2

    # Mongo versions of operations
    MONGO_OPS = {'>': '$gt', '>=': '$gte',
                 '<': '$lt', '<=': '$lte',
                 ConstraintOperator.EXISTS: '$exists',
                 ConstraintOperator.SIZE: '$size',
                 ConstraintOperator.TYPE: '$type',
                 '!=': '$ne', '=': None
    }

    # Javascript version of operations, for $where clauses
    JS_OPS = {'=': '=='}  # only different ones need to be here

    # Reverse-mapping of operations
    MONGO_OPS_REV = {v: k for k, v in MONGO_OPS.iteritems()
                     if v is not None}

    # Map of Python types to Javascript type names
    JS_TYPES = {Number: 'number', str: 'string', bool: 'boolean'}

    def __init__(self, constraint, rev=True, exists_main=False):
        """Create new clause from a constraint.

        :param constraint: The constraint
        :type constraint: Constraint
        :param rev: Whether to reverse the sense of the constraint, i.e. in order
        to select records that do not meet it.
        :type rev: bool
        :param exists_main: Put exists into main clause
        :type exists_main: bool
        :raise: AssertionError if constraint is None

        """
        assert constraint is not None
        self._rev = rev
        self._loc, self._expr = self._create(constraint, exists_main)
        self._constraint = constraint

    @property
    def query_loc(self):
        """Where this clause should go in the query.
        The two possible values are enumerated by variables in this class:

        - MongoClause.LOC_MAIN
        - MongoClause.LOC_WHERE

        :return: Location code
        :rtype: int
        """
        return self._loc

    @property
    def expr(self):
        """Query expression
        """
        return self._expr

    @property
    def constraint(self):
        return self._constraint

    def _create(self, constraint, exists_main):
        """Create MongoDB query clause for a constraint.

        :param constraint: The constraint
        :type constraint: Constraint
        :param exists_main: Put exists into main clause
        :type exists_main: bool
        :return: New clause
        :rtype: MongoClause
        :raise: ValueError if value doesn't make sense for operator
        """
        c = constraint  # alias
        op = self._reverse_operator(c.op) if self._rev else c.op
        mop = self._mongo_op_str(op)
        # build the clause parts: location and expression
        loc = MongoClause.LOC_MAIN  # default location
        if op.is_exists():
            loc = MongoClause.LOC_MAIN2 if exists_main else MongoClause.LOC_MAIN
            assert(isinstance(c.value, bool))
            # for exists, reverse the value instead of the operator
            not_c_val = not c.value if self._rev else c.value
            expr = {c.field.name: {mop: not_c_val}}
        elif op.is_size():
            if op.is_variable():
                # variables only support equality, and need to be in $where
                loc = MongoClause.LOC_WHERE
                js_op = '!=' if self._rev else '=='
                expr = 'this.{}.length {} this.{}'.format(c.field.name, js_op, c.value)
            elif op.is_size_eq() and not self._rev:
                expr = {c.field.name: {'$size': c.value}}
            else:
                # inequalities also need to go into $where clause
                self._check_size(op, c.value)
                loc = MongoClause.LOC_WHERE
                szop = ConstraintOperator(op.size_op)
                if self._rev:
                    szop.reverse()
                js_op = self._js_op_str(szop)
                expr = 'this.{}.length {} {}'.format(c.field.name, js_op, c.value)
        elif op.is_type():
            loc = MongoClause.LOC_WHERE
            type_name = self.JS_TYPES.get(c.value, None)
            if type_name is None:
                raise RuntimeError('Could not get JS type for {}'.format(c.value))
            typeop = '!=' if self._rev else '=='
            expr = 'typeof this.{} {} "{}"'.format(c.field.name, typeop, type_name)
        else:
            if mop is None:
                expr = {c.field.name: c.value}
            elif isinstance(c.value, bool):
                # can simplify boolean {a: {'$ne': True/False}} to {a: False/True}
                not_c_val = not c.value if self._rev else c.value
                expr = {c.field.name: not_c_val}
            else:
                expr = {c.field.name: {mop: c.value}}
        return loc, expr

    def _check_size(self, op, value):
        if not isinstance(value, int):
            raise ValueError('wrong type for size: {}'.format(value))
        if value < 0:
            raise ValueError('negative value for size: {}'.format(value))
        if op.is_size_lt() and value == 0:
            raise ValueError('value 0 is not allowed for size operator "{}"'.format(op))

    def _reverse_operator(self, op):
        """Reverse the operation e.g. since the conditions
        you provide are assertions of how things should be,
        e.g. asserting (a > b) leads to a search for (a <= b)

        :param op: Operator for any field/value
        :type op: ConstraintOperator
        """
        op = copy.copy(op)
        op.reverse()
        # check that we can map it
        if not str(op) in self.MONGO_OPS:
            raise ValueError('unknown operator: {}'.format(op))
        return op

    def _mongo_op_str(self, op):
        """Get the MongoDB string for an operator
        """
        return self.MONGO_OPS[str(op)]

    def _js_op_str(self, op):
        """Get JavaScript inequality operator equivalent
        """
        return self.JS_OPS.get(str(op), op)


class MongoQuery:
    """MongoDB query composed of MongoClause objects.
    """
    def __init__(self):
        """Create empty query.
        """
        self._main, self._where = [], []
        self._main2 = []

    def add_clause(self, clause):
        """Add a new clause to the existing query.

        :param clause: The clause to add
        :type clause: MongoClause
        :return: None
        """
        if clause.query_loc == MongoClause.LOC_MAIN:
            self._main.append(clause)
        elif clause.query_loc == MongoClause.LOC_MAIN2:
            self._main2.append(clause)
        elif clause.query_loc == MongoClause.LOC_WHERE:
            self._where.append(clause)
        else:
            raise RuntimeError('bad clause location: {}'.format(clause.query_loc))

    def to_mongo(self, disjunction=True):
        """Create from current state a valid MongoDB query expression.

        :return: MongoDB query expression
        :rtype: dict
        """
        q = {}
        # add all the main clauses to `q`
        clauses = [e.expr for e in self._main]
        if clauses:
            if disjunction:
                if len(clauses) + len(self._where) > 1:
                    q['$or'] = clauses
                else:
                    # simplify 'or' of one thing
                    q.update(clauses[0])
            else:
                for c in clauses:
                    q.update(c)
        # add all the main2 clauses; these are not or'ed
        for c in (e.expr for e in self._main2):
            # add to existing stuff for the field
            for field in c:
                if field in q:
                    q[field].update(c[field])
                else:
                    q.update(c)
        # add where clauses, if any, to `q`
        if self._where:
            where_clause = ' || '.join([w.expr for w in self._where])
            if disjunction:
                if not '$or' in q:
                    q['$or'] = []
                q['$or'].append({'$where': where_clause})
            else:
                q['$where'] = where_clause
        return q

    @property
    def where_clauses(self):
        return self._where

    @property
    def clauses(self):
        return self._main

    @property
    def all_clauses(self):
        return self._main + self._where


class Projection:
    """Fields on which to project the query results.
    """
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

    def to_mongo(self):
        """Translate projection to MongoDB query form.

        :return: Dictionary to put into a MongoDB JSON query
        :rtype: dict
        """
        d = copy.copy(self._fields)
        for k, v in self._slices.iteritems():
            d[k] = {'$slice': v}
        return d


class ConstraintViolation:
    """A single constraint violation, with no metadata.
    """
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
        return str(self._constraint.op)

    @property
    def got_value(self):
        return self._got

    @property
    def expected_value(self):
        return self._expected


class ConstraintViolationGroup:
    """A group of constraint violations with metadata.
    """
    def __init__(self):
        """Create an empty object.
        """
        self._viol = []
        # These are read/write
        self.subject = ''
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


class ProgressMeter:
    """Simple progress tracker
    """
    def __init__(self, num, fmt):
        self._n = num
        self._subject = '?'
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
        sys.stderr.write('\n')
        sys.stderr.flush()
        self._count = 0


class ConstraintSpec(object):
    """Specification of a set of constraints for a collection.
    """
    FILTER_SECT = 'filter'
    CONSTRAINT_SECT = 'constraints'
    SAMPLE_SECT = 'sample'

    def __init__(self, spec):
        """Create specification from a configuration.

        :param spec: Configuration for a single collection
        :type spec: dict
        :raise: ValueError if specification is wrong
        """
        self._sections, _slist = {}, []
        for item in spec:
            if isinstance(item, dict):
                self._add_complex_section(item)
            else:
                self._add_simple_section(item)

    def values(self):
        """Return a list of all the sections.

        :rtype: list(ConstraintSpecSection)
        """
        sect = []
        # simple 1-level flatten operation
        for values in self._sections.itervalues():
            for v in values:
                sect.append(v)
        return sect

    def _add_complex_section(self, item):
        """Add a section that has a filter and set of constraints

        :raise: ValueError if filter or constraints is missing
        """
        # extract filter and constraints
        try:
            fltr = item[self.FILTER_SECT]
        except KeyError:
            raise ValueError("configuration requires '{}'".format(self.FILTER_SECT))
        sample = item.get(self.SAMPLE_SECT, None)
        constraints = item.get(self.CONSTRAINT_SECT, None)

        section = ConstraintSpecSection(fltr, constraints, sample)
        key = section.get_key()
        if key in self._sections:
            self._sections[key].append(section)
        else:
            self._sections[key] = [section]

    def _add_simple_section(self, item):
        self._sections[None] = ConstraintSpecSection(None, item, None)


class ConstraintSpecSection(object):
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
    """Validate a collection.
    """

    # Parse a single constraint
    _relation_re = re.compile(r'''\s*
        ([a-zA-Z_.0-9]+(?:/[a-zA-Z_.0-9]+)?)\s*         # Identifier
        (<=?|>=?|!?=|exists|        # Operator (1)
        type|                       # Operator (1a)
        size[><$]?)\s*              # operator (2)
        ([-]?\d+(?:\.\d+)?|         # Value: number
            \'[^\']+\'|             #   single-quoted string
            \"[^"]+\"|              #   double-quoted string
            [Tt]rue|[Ff]alse|       #   boolean
            [a-zA-Z_][a-zA-Z_.0-9]* # variable name
        )
        \s*''', re.VERBOSE)

    def __init__(self, max_violations=50, max_dberrors=10, aliases=None, add_exists=False):
        DoesLogging.__init__(self, name='mg.validator')
        self.set_progress(0)
        self._aliases = aliases if aliases else {}
        self._max_viol = max_violations
        if self._max_viol > 0:
            self._find_kw = {'limit': self._max_viol}
        else:
            self._find_kw = {}
        self._max_dberr = max_dberrors
        self._base_report_fields = {'_id': 1, 'task_id': 1}
        self._add_exists = add_exists

    def set_aliases(self, a):
        """Set aliases.
        """
        self._aliases = a

    def set_progress(self, num):
        """Report progress every `num` bad records.

        :param num: Report interval
        :type num: int
        :return: None
        """
        report_str = 'Progress for {subject}: {count:d} invalid, {:d} db errors, {:d} bytes'
        self._progress = ProgressMeter(num, report_str)

    def num_violations(self):
        if self._progress is None:
            return 0
        return self._progress._count

    def validate(self, coll, constraint_spec, subject='collection'):
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
        """
        self._spec = constraint_spec
        self._progress.set_subject(subject)
        self._build(constraint_spec)
        for cond, body, sampler in self._sections:
            cvg = self._validate_section(subject, coll, cond, body, sampler)
            if cvg is not None:
                yield cvg

    def _validate_section(self, subject, coll, cond, body, sampler):
        """Validate one section of a spec.

        :param subject: Name of subject
        :type subject: str
        :param coll: The collection to validate
        :type coll: pymongo.Collection
        :param cond: Condition to filter records
        :type cond: MongoQuery
        :param body: Main set of constraints
        :type body: MongoQuery
        :param sampler: Sampling class if any
        :type sampler: Sampler
        :return: Group of constraint violations, if any, otherwise None
        :rtype: ConstraintViolationGroup or None
        """
        query = cond.to_mongo(disjunction=False)
        query.update(body.to_mongo())
        cvgroup = ConstraintViolationGroup()
        cvgroup.subject = subject
        cvgroup.condition = cond.to_mongo(disjunction=False)
        self._log.debug('Query spec: {}'.format(query))
        self._log.debug('Query fields: {}'.format(self._report_fields))
        # Find records that violate 1 or more constraints
        cursor = coll.find(query, fields=self._report_fields, **self._find_kw)
        if sampler is not None:
            cursor = sampler.sample(cursor)
        nbytes, num_dberr, num_rec = 0, 0, 0
        while 1:
            try:
                record = cursor.next()
                nbytes += total_size(record)
                num_rec += 1
            except StopIteration:
                self._log.info("collection {}: {:d} records, {:d} bytes, {:d} db-errors"
                               .format(subject, num_rec, nbytes, num_dberr))
                break
            except pymongo.errors.PyMongoError, err:
                num_dberr += 1
                if num_dberr > self._max_dberr > 0:
                    raise DBError("Too many errors")
                self._log.warn("DB.{:d}: {}".format(num_dberr, err))
                continue

            # report progress
            if self._progress:
                self._progress.update(num_dberr, nbytes)
            # get reasons for badness
            violations = self._get_violations(body, record)
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
        reasons = []
        for clause in query.all_clauses:
            key = clause.constraint.field.name
            op = clause.constraint.op
            fval = mongo_get(record, key)
            # retrieve value of variable
            if op.is_variable():
                varname = fval
                fval = mongo_get(record, varname)
                if fval is None:
                    reasons.append(ConstraintViolation(clause.constraint, 'missing', varname))
                    continue
            # take length for size
            if op.is_size():
                if isinstance(fval, basestring) or not hasattr(fval, '__len__'):
                    reasons.append(ConstraintViolation(clause.constraint, type(fval), 'sequence'))
                    continue
                fval = len(fval)
            ok, expected = clause.constraint.passes(fval)
            if not ok:
                reasons.append(ConstraintViolation(clause.constraint, fval, expected))
        return reasons

    def _build(self, constraint_spec):
        """Generate queries to execute.

        Sets instance variables so that Mongo query strings, etc. can now
        be extracted from the object.

        :param constraint_spec: Constraint specification
        :type constraint_spec: ConstraintSpec
        """
        self._sections = []
        self._report_fields = self._base_report_fields
        # loopover each condition on the records
        for sval in constraint_spec.values():
            #print("@@ CONDS = {}".format(cond_expr_list))
            #print("@@ MAIN = {}".format(expr_list))
            groups = self._process_constraint_expressions(sval.constraints)
            projection = Projection()
            query = MongoQuery()
            for cg in groups.itervalues():
                for c in cg:
                    projection.add(c.field, c.op, c.value)
                    query.add_clause(MongoClause(c))
                if self._add_exists:
                    for c in cg.existence_constraints:
                        query.add_clause(MongoClause(c, exists_main=True))
            self._report_fields.update(projection.to_mongo())
            cond_query = MongoQuery()
            if sval.filters is not None:
                cond_groups = self._process_constraint_expressions(sval.filters, rev=False)
                for cg in cond_groups.itervalues():
                    for c in cg:
                        cond_query.add_clause(MongoClause(c, rev=False))
            self._sections.append((cond_query, query, sval.sampler))

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
            field, raw_op, val = self._parse_expr(expr)
            op = ConstraintOperator(raw_op)
            if field not in groups:
                groups[field] = ConstraintGroup(Field(field, self._aliases))
            groups[field].add_constraint(op, val)

        # add existence constraints
        for cgroup in groups.itervalues():
            cgroup.add_existence(rev)

        # optionally check for conflicts
        if conflict_check:
            # check for conflicts in each group
            for field_name, group in groups.iteritems():
                conflicts = group.get_conflicts()
                if conflicts:
                    raise ValueError('Conflicts for field {}: {}'.format(field_name, conflicts))
        return groups

    def set_aliases(self, new_value):
        "Set aliases and wrap errors in ValueError"
        try:
            self.aliases = new_value
        except Exception, err:
            raise ValueError("invalid value: {}".format(err))

    def _parse_expr(self, e):
        m = self._relation_re.match(e)
        if m is None:
            raise ValueError("error parsing expression '{}'".format(e))
        field, op, val = m.groups()
        # Try different types
        try:
            # Integer
            val_int = int(val)
            val = val_int
        except ValueError:
            try:
                # Float
                val_float = float(val)
                val = val_float
            except ValueError:
                try:
                    # Boolean
                    val = {'true': True, 'false': False}[val.lower()]
                except KeyError:
                    # String
                    if re.match(r'".*"|\'.*\'', val):
                        # strip quotes from strings
                        val = val[1:-1]
        return field, op, val


class Sampler(object):
    """Randomly sample a proportion of the full collection.
    """

    # Random uniform distribution
    DIST_RUNIF = 1
    # Default distribution
    DEFAULT_DIST = DIST_RUNIF
    # Names of distributions
    DIST_CODES = {'uniform': DIST_RUNIF}

    def __init__(self, min_items=0, max_items=1e9, p=1.0, distrib=DEFAULT_DIST, **kw):
        """Create new parameterized sampler.

        :param min_items: Minimum number of items in the sample
        :param max_items: Maximum number of items in the sample
        :param p: Probability of selecting an item
        :param distrib: Probability distribution code, one of DIST_<name> in this class
        :type distrib: str or int
        :raise: ValueError, if `distrib` is an unknown code or string
        """
        # Sanity checks
        if min_items < 0:
            raise ValueError('min_items cannot be negative ({:d})'.format(min_items))
        if (max_items != 0) and (max_items < min_items):
            raise ValueError('max_items must be zero or >= min_items ({:d} < {:d})'.format(max_items, min_items))
        if not (0.0 <= p <= 1.0):
            raise ValueError('probability, p, must be between 0 and 1 ({:f})'.format(p))
        self.min_items = min_items
        self.max_items = max_items
        self.p = p
        self._empty = True
        # Distribution
        if not isinstance(int, distrib):
            distrib = self.DIST_CODES.get(str(distrib), None)
        if distrib == self.DIST_RUNIF:
            self._skip_fn = self._runif
        else:
            raise ValueError("unrecognized distribution: {}".format(distrib))

    @property
    def is_empty(self):
        return self._empty

    def _runif(self, x, alpha):
        """Skip ahead x +/- alpha steps in a uniform distribution.
        """
        return random.uniform(x - alpha, x + alpha)

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

        # select `n_target` items
        mu = 1. * count / n_target     # mean items between results
        alpha = 0.25 * mu              # +/- slop in items between results
        n, offs = 0, 0                 # number returned, position in collection
        while n < n_target:
            max_offs = count - (n_target - n)
            max_skip = max_offs - offs - 1
            skip = min(max_skip, int(round(self._skip_fn(mu, alpha))))
            for _ in xrange(skip):
                cursor.next()
            # give next item to caller
            yield cursor.next()
            n += 1
            offs += skip