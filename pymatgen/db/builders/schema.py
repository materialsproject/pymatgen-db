"""
Utility module for schema validation, for builder testing
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "11/1/13"

import datetime
import glob
import json
import os
import re
import time

# Default schema version
DEFAULT_VERSION = "1.0.0"

# Indicates any version
ANY_VERSION = "*.*.*"

# denotes optional field/scalar
OPTIONAL_FLAG = "?"

# marker of specialness
SPECIAL = "__"
SPECIAL_LEN = len(SPECIAL)

# Regex for values
# Note that the special prefix/suffix is optional
VALUE_RE = re.compile(r"(?:{spec})?([a-zA-Z]+)(?:{spec})?\s*(.*)".format(spec=SPECIAL))

# Global obj with all collected schemas
schemata = {}


class SchemaError(Exception):
    """Base class of all errors raised by schema creation or validation."""

    pass


class SchemaTypeError(SchemaError):
    def __init__(self, typename):
        SchemaError.__init__(self, f"bad type ({typename})")


class SchemaPathError(SchemaError):
    pass


class SchemaParseError(SchemaError):
    pass


def add_schemas(path, ext="json"):
    """Add schemas from files in 'path'.

    :param path: Path with schema files. Schemas are named by their file,
                 with the extension stripped. e.g., if path is "/tmp/foo",
                 then the schema in "/tmp/foo/bar.json" will be named "bar".
    :type path: str
    :param ext: File extension that identifies schema files
    :type ext: str
    :return: None
    :raise: SchemaPathError, if no such path. SchemaParseError, if a schema
            is not valid JSON.
    """
    if not os.path.exists(path):
        raise SchemaPathError()
    filepat = "*." + ext if ext else "*"
    for f in glob.glob(os.path.join(path, filepat)):
        with open(f) as fp:
            try:
                schema = json.load(fp)
            except ValueError:
                raise SchemaParseError(f"error parsing '{f}'")
        name = os.path.splitext(os.path.basename(f))[0]
        schemata[name] = Schema(schema)


def get_schema(name):
    """Get schema by name

    :param name: name of schema
    :type name: str
    :return: new schema
    :rtype: Schema
    :raise: KeyError, if schema is not found
    """
    return schemata[name]


def load_schema(file_or_fp):
    """Load schema from file.

    :param file_or_fp: File name or file object
    :type file_or_fp: str, file
    :raise: IOError if file cannot be opened or read, ValueError if
            file is not valid JSON or JSON is not a valid schema.
    """
    fp = open(file_or_fp) if isinstance(file_or_fp, str) else file_or_fp
    obj = json.load(fp)
    schema = Schema(obj)
    return schema


## Validator classes


class HasMeta:
    """Mix-in class to handle metadata.
    Adds the 'meta' class attribute.
    """

    FIELD_SEP = ","
    KV_SEP = ":"

    def __init__(self, meta):
        """Create with new metadata (which may be empty).
        The metadata should be dict-like (i.e. __getitem__ and __setitem__) or
        be a string in the format "name1: value1, name2: value2, ...", where the
        white space is optional.

        :param meta: Init with this metadata.
        :type meta: str or dict
        """
        if not meta:
            self.meta = {}
        elif isinstance(meta, str):
            # build a dict from key-value pairs
            parts = meta.split(self.FIELD_SEP)
            self.meta = {k: v for k, v in map(lambda fld: fld.split(":", 1), parts)}
        else:
            # assume dict-like
            self.meta = meta

    def add_meta(self, key, value):
        self.meta[key] = value


class Schema(HasMeta):

    # enum for navigating hierarchies
    IS_LIST, IS_DICT, IS_SCALAR = 0, 1, 2

    def __init__(self, schema, optional=False, meta=""):
        HasMeta.__init__(self, meta)
        self.is_optional = optional
        self._schema = self._parse(schema)
        self._json_schema = None
        self._json_schema_keys = {}

    def validate(self, doc, path="(root)"):
        t = self._whatis(doc)
        if t != self._type:
            return self._vresult(path, "type mismatch: {} != {}", self._typestr(t), self)
        if t == self.IS_LIST:
            if len(doc) == 0:
                return None
            return self._schema[0].validate(doc[0], path=path + "[0]")
        elif t == self.IS_DICT:
            # fail if document is missing any required keys
            dkeys = set(doc.keys())
            skeys = set(filter(lambda k: not self._schema[k].is_optional, self._schema.keys()))
            if skeys - dkeys:
                return self._vresult(path, "missing keys: ({})".format(", ".join(skeys - dkeys)))
            # check each item in document
            for k, v in doc.items():
                if k in self._schema:
                    result = self._schema[k].validate(doc[k], path=path + "." + k)
                    if result is not None:
                        return result
                else:
                    pass  # do nothing for 'extra' keys
                    # return self._vresult(path, "missing key: {}", k)
        else:
            if not self._schema.check(doc):
                return self._vresult(path, "bad value '{}' for type {}", doc, self._schema)

    def json_schema(self, **add_keys):
        """Convert our compact schema representation to the standard, but more verbose,
        JSON Schema standard.

        Example JSON schema: http://json-schema.org/examples.html
        Core standard: http://json-schema.org/latest/json-schema-core.html

        :param add_keys: Key, default value pairs to add in,
                         e.g. description=""
        """
        self._json_schema_keys = add_keys
        if self._json_schema is None:
            self._json_schema = self._build_schema(self._schema)
        return self._json_schema

    def _build_schema(self, s):
        """Recursive schema builder, called by `json_schema`."""
        w = self._whatis(s)
        if w == self.IS_LIST:
            w0 = self._whatis(s[0])
            js = {"type": "array", "items": {"type": self._jstype(w0, s[0])}}
        elif w == self.IS_DICT:
            js = {
                "type": "object",
                "properties": {key: self._build_schema(val) for key, val in s.items()},
            }
            req = [key for key, val in s.items() if not val.is_optional]
            if req:
                js["required"] = req
        else:
            js = {"type": self._jstype(w, s)}
        for k, v in self._json_schema_keys.items():
            if k not in js:
                js[k] = v
        return js

    def _jstype(self, stype, sval):
        """Get JavaScript name for given data type, called by `_build_schema`."""
        if stype == self.IS_LIST:
            return "array"
        if stype == self.IS_DICT:
            return "object"
        if isinstance(sval, Scalar):
            return sval.jstype
        # it is a Schema, so return type of contents
        v = sval._schema
        return self._jstype(self._whatis(v), v)

    def _vresult(self, path, fmt, *args):
        meta_info = ""
        if self.meta and "desc" in self.meta:
            meta_info = '="{}"'.format(self.meta["desc"])
        return f"{path}{meta_info}: " + fmt.format(*args)

    def _parse(self, value):
        t = self._type = self._whatis(value)
        if t == self.IS_LIST:
            return [Schema(value[0])]
        elif t == self.IS_DICT:
            r = {}
            for k, v in value.items():
                # skip metadata keys
                if k.startswith(SPECIAL) and k.endswith(SPECIAL):
                    self.add_meta(k[SPECIAL_LEN:-SPECIAL_LEN], v)
                    continue
                # look for optional flag at start of key
                opt_flag = self.is_optional
                if k[0] == OPTIONAL_FLAG:
                    k = k[1:]
                    opt_flag = True
                elif k in ("@class", "@module"):  # optionalize the cruft
                    opt_flag = True
                # parse value and assign
                r[k] = Schema(v, optional=opt_flag)
            return r
        else:
            optional = self.is_optional
            if len(value) and value[0] == OPTIONAL_FLAG:
                value = value[1:]
                optional = True
            vinfo = VALUE_RE.match(value)
            if not vinfo:
                raise ValueError(f"bad type format, must be __<type>__ got {value}")
            dtype, meta = vinfo.groups()
            return Scalar(dtype, optional=optional, meta=meta)

    def _whatis(self, obj):
        if isinstance(obj, list):
            return self.IS_LIST
        elif isinstance(obj, dict):
            return self.IS_DICT
        return self.IS_SCALAR

    def _typestr(self, t):
        return ("list", "dict", "scalar")[t]

    def __str__(self):
        return self._typestr(self._type)

    def __repr__(self):
        return f"document::{self}"


def _is_datetime(d):
    return isinstance(d, datetime.datetime) or isinstance(d, time.struct_time)


class Scalar(HasMeta):
    # For each typecode, a function that returns True/False on whether
    # its argument matches.

    TYPES = {
        "string": lambda x: isinstance(x, str),
        "bool": lambda x: x is True or x is False,
        "datetime": _is_datetime,
        "date": _is_datetime,
        "float": lambda x: isinstance(x, float),
        "int": lambda x: isinstance(x, int),
        "null": lambda x: x is None,
        "array": lambda x: isinstance(x, list),
        "object": lambda x: isinstance(x, dict),
    }

    def __init__(self, typecode, optional=False, meta=""):
        self.is_optional = optional
        self._type = typecode
        HasMeta.__init__(self, meta)
        try:
            self.check = self.TYPES[typecode]
        except KeyError:
            raise SchemaTypeError(typecode)

    JSTYPES = {
        "datetime": "string",
        "date": "string",
        "string": "string",
        "bool": "boolean",
        "int": "integer",
        "float": "number",
        "null": "null",
    }

    @property
    def jstype(self):
        """Return JavaScript type."""
        return self.JSTYPES[self._type]

    def __str__(self):
        return self._type

    def __repr__(self):
        return f"scalar::{self}"
