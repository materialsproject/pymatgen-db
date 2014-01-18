"""
Utility module for schema validation, for builder testing
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '11/1/13'

import datetime
import re
import time

# Default schema version
DEFAULT_VERSION = 1

# denotes optional field/scalar
OPTIONAL_FLAG = '?'

# marker of specialness
SPECIAL = '__'
SPECIAL_LEN = len(SPECIAL)

# Regex for values
# Note that the special prefix/suffix is optional
VALUE_RE = re.compile("(?:{spec})?([a-zA-Z]+)(?:{spec})?\s*(.*)"
                      .format(spec=SPECIAL))


class SchemaError(Exception):
    """Base class of all errors raised by schema creation or validation.
    """
    pass


class SchemaTypeError(SchemaError):
    def __init__(self, typename):
        SchemaError.__init__(self, "bad type ({})".format(typename))

class SchemaVersionError(SchemaError):
    def __init__(self, version):
        SchemaError.__init__(self, "bad version ({})".format(version))


def get_schema(collection, version=DEFAULT_VERSION):
    """Get schema for collection.

    :param collection: name of collection
    :type collection: str
    :return: new schema
    :rtype: Schema
    :raise: SchemaVersionError
    """
    try:
        sv = schemata[version]
    except KeyError:
        raise SchemaVersionError(version)
    spec = sv.get(collection, None)
    result = Schema("__null__") if spec is None else Schema(spec)
    return result

## Validator classes


class HasMeta(object):
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
        elif isinstance(meta, basestring):
            # build a dict from key-value pairs
            parts = meta.split(self.FIELD_SEP)
            self.meta = {k: v for k, v in map(lambda fld: fld.split(':', 1), parts)}
        else:
            # assume dict-like
            self.meta = meta

    def add_meta(self, key, value):
        self.meta[key] = value


class Schema(HasMeta):

    # enum for navigating hierarchies
    IS_LIST, IS_DICT, IS_SCALAR = 0, 1, 2

    def __init__(self, schema, optional=False, meta=''):
        HasMeta.__init__(self, meta)
        self.is_optional = optional
        self._schema = self._parse(schema)
        self._json_schema = None

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
            skeys = set(filter(lambda k: not self._schema[k].is_optional,  self._schema.iterkeys()))
            if skeys - dkeys:
                return self._vresult(path, "missing keys: ({})".format(', '.join(skeys - dkeys)))
            # check each item in document
            for k, v in doc.iteritems():
                if self._schema.has_key(k):
                    result = self._schema[k].validate(doc[k], path=path + "." + k)
                    if result is not None:
                        return result
                else:
                    pass  # do nothing for 'extra' keys
                    #return self._vresult(path, "missing key: {}", k)
        else:
            if not self._schema.check(doc):
                return self._vresult(path, "bad value '{}' for type {}",
                                     doc, self._schema)

    @property
    def json_schema(self):
        """Convert our compact schema representation to the standard, but more verbose,
        JSON Schema standard.

        Example JSON schema: http://json-schema.org/examples.html
        Core standard: http://json-schema.org/latest/json-schema-core.html
        """
        if self._json_schema is None:
            self._json_schema = self._build_schema(self._schema)
        return self._json_schema

    def _build_schema(self, s):
        """Recursive schema builder, called by `json_schema`.
        """
        w = self._whatis(s)
        if w == self.IS_LIST:
            w0 = self._whatis(s[0])
            js = {"type": "array",
                  "items": {"type": self._jstype(w0, s[0])}}
        elif w == self.IS_DICT:
            js = {"type": "object",
                  "properties": {key: self._build_schema(val) for key, val in s.iteritems()}}
            req = [key for key, val in s.iteritems() if not val.is_optional]
            if req:
                js["required"] = req
        else:
            js = {"type": self._jstype(w, s)}
        return js

    def _jstype(self, stype, sval):
        """Get JavaScript name for given data type, called by `_build_schema`.
        """
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
        meta_info = ''
        if self.meta and self.meta.has_key('desc'):
            meta_info = '="{}"'.format(self.meta['desc'])
        return "{}{}: ".format(path, meta_info) + fmt.format(*args)

    def _parse(self, value):
        t = self._type = self._whatis(value)
        if t == self.IS_LIST:
            return [Schema(value[0])]
        elif t == self.IS_DICT:
            r = {}
            for k, v in value.iteritems():
                # skip metadata keys
                if k.startswith(SPECIAL) and k.endswith(SPECIAL):
                    self.add_meta(k[SPECIAL_LEN:-SPECIAL_LEN], v)
                    continue
                # look for optional flag at start of key
                opt_flag = self.is_optional
                if k[0] == OPTIONAL_FLAG:
                    k = k[1:]
                    opt_flag = True
                elif k in ('@class', '@module'):  # optionalize the cruft
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
                raise ValueError("bad type format, must be __<type>__ got {}"
                                 .format(value))
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
        return "document::{}".format(self)


def _is_datetime(d):
    return isinstance(d, datetime.datetime) or \
        isinstance(d, time.struct_time)


class Scalar(HasMeta):
    # For each typecode, a function that returns True/False on whether
    # its argument matches.

    TYPES = {
        'string': lambda x: isinstance(x, basestring),
        'bool': lambda x: x is True or x is False,
        'datetime': _is_datetime,
        'date': _is_datetime,
        'float': lambda x: isinstance(x, float),
        'int': lambda x: isinstance(x, int),
        'null': lambda x: x is None,
        'array': lambda x: isinstance(x, list),
        'object': lambda x: isinstance(x, dict)
    }

    def __init__(self, typecode, optional=False, meta=''):
        self.is_optional = optional
        self._type = typecode
        HasMeta.__init__(self, meta)
        try:
            self.check = self.TYPES[typecode]
        except KeyError:
            raise SchemaTypeError(typecode)

    JSTYPES = {
        "datetime": "string", "date": "string",
        "string": "string",
        "bool": "boolean",
        "int": "integer",
        "float": "number",
        "null": "null"
    }

    @property
    def jstype(self):
        """Return JavaScript type.
        """
        return self.JSTYPES[self._type]

    def __str__(self):
        return self._type

    def __repr__(self):
        return "scalar::{}".format(self)

## Inline  schema

schemata = {
    1: dict(
        materials={
            "?anonymous_formula": {"A": "__float__"},
            "?band_gap": {"optimize_structure_gap": {"is_direct": "__int__"},
                         "search_gap": {"is_direct": "__int__"}},
            "?bv_structure": {"@class": "__string__",
                             "@module": "__string__",
                             "lattice": {"@class": "__string__",
                                         "@module": "__string__",
                                         "a": "__float__",
                                         "alpha": "__float__",
                                         "b": "__float__",
                                         "beta": "__float__",
                                         "c": "__float__",
                                         "gamma": "__float__",
                                         "volume": "__float__"},
                             "sites": [{"label": "__string__",
                                        "species": [{"@class": "__string__",
                                                     "@module": "__string__",
                                                     "element": "__string__",
                                                     "occu": "__int__"}]}]},
            "chemsys": "__string__",
            "?cif": "__string__",
            "?cifs": {"conventional_standard": "__string__",
                     "primitive": "__string__",
                     "refined": "__string__"},
            "?cpu_time": "__float__",
            "?created_at": "__date__",
            "?decomposes_to": [{"formula": "__string__", "task_id": "__string__"}],
            "?delta_volume": "__float__",
            "density": "__float__",
            "?efermi": "__float__",
            "?encut": "__float__",
            "final_energy": "__float__",
            "final_energy_per_atom": "__float__",
            "formation_energy_per_atom": "__float__",
            "full_formula": "__string__",
            "initial_structure": {"@class": "__string__",
                                  "@module": "__string__",
                                  "lattice": {"@class": "__string__",
                                              "@module": "__string__",
                                              "a": "__float__",
                                              "alpha": "__float__",
                                              "b": "__float__",
                                              "beta": "__float__",
                                              "c": "__float__",
                                              "gamma": "__float__",
                                              "volume": "__float__"},
                                  "?sites": [{"label": "__string__",
                                             "species": [{"@class": "__string__",
                                                          "@module": "__string__",
                                                          "element": "__string__",
                                                          "occu": "__int__"}]}]},
            "?ionic_steps": [[{"electronic_steps": [{"XCdc": "__float__",
                                                    "alphaZ": "__float__",
                                                    "atom": "__float__",
                                                    "bandstr": "__float__",
                                                    "e_0_energy": "__float__",
                                                    "e_fr_energy": "__float__",
                                                    "e_wo_entrp": "__float__",
                                                    "eentropy": "__float__",
                                                    "ewald": "__float__",
                                                    "hartreedc": "__float__",
                                                    "pawaedc": "__float__",
                                                    "pawpsdc": "__float__"}],
                              "structure": {"@class": "__string__",
                                            "@module": "__string__",
                                            "lattice": {"@class": "__string__",
                                                        "@module": "__string__",
                                                        "a": "__float__",
                                                        "alpha": "__float__",
                                                        "b": "__float__",
                                                        "beta": "__float__",
                                                        "c": "__float__",
                                                        "gamma": "__float__",
                                                        "volume": "__float__"},
                                            "sites": [{"label": "__string__",
                                                       "species": [{"@class": "__string__",
                                                                    "@module": "__string__",
                                                                    "element": "__string__",
                                                                    "occu": "__int__"}]}]}}]],
            "is_compatible": "__int__",
            "is_hubbard": "__int__",
            "is_ordered": "__bool__",
            "nelements": "__int__",
            "nkpts": "__int__",
            "nsites": "__int__",
            "ntask_ids": "__int__",
            "oxide_type": "__string__",
            "pretty_formula": "__string__",
            "?pseudo_potential": {"functional": "__string__",
                                 "pot_type": "__string__"},
            "?run_stats": {"overall": {"Elapsed time (sec)": "__float__",
                                      "System time (sec)": "__float__",
                                      "Total CPU time used (sec)": "__float__",
                                      "User time (sec)": "__float__"},
                          "relax1": {"Average memory used (kb)": "__float__",
                                     "Elapsed time (sec)": "__float__",
                                     "Maximum memory used (kb)": "__float__",
                                     "System time (sec)": "__float__",
                                     "Total CPU time used (sec)": "__float__",
                                     "User time (sec)": "__float__"},
                          "relax2": {"Average memory used (kb)": "__float__",
                                     "Elapsed time (sec)": "__float__",
                                     "Maximum memory used (kb)": "__float__",
                                     "System time (sec)": "__float__",
                                     "Total CPU time used (sec)": "__float__",
                                     "User time (sec)": "__float__"}},
            "run_type": "__string__",
            "snl_final": {
                "__desc__": "Final structure metadata",
                  "@class": "__string__",
                  "@module": "__string__",
                  "about": {
                      "?_icsd": {"icsd_id": "__int__"},
                      "created_at": "__datetime__",
                      "references": "__string__",
                      "history": [
                            {"url": "__string__",
                             "name": "__string__",
                             "description": {
                                 "?icsd_id": "__int__"
                             }
                            }
                        ]
                  },
                "anonymized_formula": "__string__",
                "chemsystem": "__string__",
                "formula": "__string__",
                "is_ordered": "__bool__",
                "is_valid": "__bool__",
                "?lattice": {"@class": "__string__",
                          "@module": "__string__",
                          "a": "__float__",
                          "alpha": "__float__",
                          "b": "__float__",
                          "beta": "__float__",
                          "c": "__float__",
                          "gamma": "__float__",
                          "volume": "__float__"},
                "nelements": "__int__",
                "nsites": "__int__",
                "reduced_cell_formula": "__string__",
                "reduced_cell_formula_abc": "__string__",
                "?sites": [{"label": "__string__",
                         "species": [{"@class": "__string__",
                                      "@module": "__string__",
                                      "element": "__string__",
                                      "occu": "__int__"}]
                        },
                        "desc:List of sites"
                       ],
                "snl_id": "__int__ desc:Structure Notation Language ID",
                "snlgroup_key": "__string__ desc:Grouping key",
                "?snlgroup_changed": "__int__",
                "?snlgroup_id": "__int__",
                "?snlgroup_id_final": "__int__"
            },
            "spacegroup": {"crystal_system": "__string__",
                           "?hall": "__string__",
                           "number": "__int__",
                           "?point_group": "__string__",
                           "?source": "__string__",
                           "?symbol": "__string__",
                           "__desc__": "Space group"},
            "structure": {"@class": "__string__",
                          "@module": "__string__",
                          "lattice": {"a": "__float__",
                                      "alpha": "__float__",
                                      "b": "__float__",
                                      "beta": "__float__",
                                      "c": "__float__",
                                      "gamma": "__float__",
                                      "volume": "__float__"},
                          "sites": [{"label": "__string__",
                                     "properties": {"?coordination_no": "__int__"},
                                     "species": [{"element": "__string__",
                                                  "occu": "__int__"}]}]},
            "?task_id": "__string__",
            "?task_type": "__string__",
            "?total_magnetization": "__float__",
            "updated_at": "__date__",
            "volume": "__float__",
            "?xrd": {"Ag": {"created_at": "__date__",
                           "updated_at": "__date__",
                           "wavelength": {"element": "__string__",
                                          "in_angstroms": "__float__"}},
                    "Cu": {"created_at": "__date__",
                           "updated_at": "__date__",
                           "wavelength": {"element": "__string__",
                                          "in_angstroms": "__float__"}},
                    "Fe": {"created_at": "__date__",
                           "updated_at": "__date__",
                           "wavelength": {"element": "__string__",
                                          "in_angstroms": "__float__"}},
                    "Mo": {"created_at": "__date__",
                           "updated_at": "__date__",
                           "wavelength": {"element": "__string__",
                                          "in_angstroms": "__float__"}}}}

    )
}
