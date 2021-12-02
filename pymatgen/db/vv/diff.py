"""
Diff collections, as sets
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "3/29/13"

# System
import logging
import re
import time

# Package
from pymatgen.db import util
from pymatgen.db.query_engine import QueryEngine
from pymatgen.db.dbconfig import normalize_auth

_log = logging.getLogger("mg.vv.diff")


class IID:
    _value = 0

    @classmethod
    def next(cls):
        cls._value += 1
        return cls._value


class Differ:
    """Calculate difference between two collections, based solely on a
    selected key.

    As noted in :func:`diff`, this will not work with huge datasets, as it stores
    all the keys in memory in order to do a "set difference" using Python sets.
    """

    #: Keys in result dictionary.
    MISSING, NEW, CHANGED = "missing", "additional", "different"

    #: CHANGED result fields
    CHANGED_MATCH_KEY = "match type"
    CHANGED_MATCH_DELTA = "delta"
    CHANGED_MATCH_EXACT = "exact"
    CHANGED_OLD = "old"
    CHANGED_NEW = "new"
    CHANGED_DELTA = "delta"

    #: for missing property
    NO_PROPERTY = "__MISSING__"

    def __init__(self, key="_id", props=None, info=None, fltr=None, deltas=None):
        """Constructor.

        :param key: Field to use for identifying records
        :param props: List of fields to use for matching records
        :param info: List of extra fields to retrieve from (and show) for each record.
        :param fltr: Filter for records, a MongoDB query expression
        :param deltas: {prop: delta} to check. 'prop' is a string, 'delta' is an instance of :class:`Delta`.
                       Any key for 'prop' not in parameter 'props' will get added.
        :type deltas: dict
        :raise: ValueError if some delta does not parse.
        """
        self._key_field = key
        self._props = [] if props is None else props
        self._info = [] if info is None else info
        self._filter = fltr if fltr else {}
        self._prop_deltas = {} if deltas is None else deltas
        self._all_props = list(set(self._props[:] + list(self._prop_deltas.keys())))

    def diff(self, c1, c2, only_missing=False, only_values=False, allow_dup=False):
        """Perform a difference between the 2 collections.
        The first collection is treated as the previous one, and the second
        is treated as the new one.

        Note: this is not 'big data'-ready; we assume all the records can fit in memory.

        :param c1: Collection (1) config file, or QueryEngine object
        :type c1: str or QueryEngine
        :param c2: Collection (2) config file, or QueryEngine object
        :type c2: str or QueryEngine
        :param only_missing: Only find and return self.MISSING; ignore 'new' keys
        :param only_values: Only find and return self.CHANGED; ignore new or missing keys
        :param allow_dup: Allow duplicate keys, otherwise fail with ValueError
        :return: dict with keys self.MISSING, self.NEW (unless only_missing is True), & self.CHANGED,
                 each a list of records with the key and
                 any other fields given to the constructor 'info' argument.
                 The meaning is: 'missing' are keys that are in c1 not found in c2
                 'new' is keys found in c2 that are not found in c1, and 'changed' are records
                 with the same key that have different 'props' values.
        """
        # Connect.
        _log.info("connect.start")
        if isinstance(c1, QueryEngine):
            engines = [c1, c2]
        else:
            engines = []
            for cfg in c1, c2:
                settings = util.get_settings(cfg)
                if not normalize_auth(settings):
                    _log.warn(f"Config file {cfg} does not have a username/password")
                settings["aliases_config"] = {"aliases": {}, "defaults": {}}
                engine = QueryEngine(**settings)
                engines.append(engine)
        _log.info("connect.end")

        # Query DB.
        keys = [set(), set()]
        eqprops = [{}, {}]
        numprops = [{}, {}]

        # Build query fields.
        fields = dict.fromkeys(self._info + self._all_props + [self._key_field], True)
        if not "_id" in fields:  # explicitly remove _id if not given
            fields["_id"] = False

        # Initialize for query loop.
        info = {}  # per-key information
        has_info, has_props = bool(self._info), bool(self._all_props)
        has_numprops, has_eqprops = bool(self._prop_deltas), bool(self._props)
        _log.info(f"query.start query={self._filter} fields={fields}")
        t0 = time.time()

        # Main query loop.
        for i, coll in enumerate(engines):
            _log.debug(f"collection {i:d}")
            count, missing_props = 0, 0
            for rec in coll.query(criteria=self._filter, properties=fields):
                count += 1
                # Extract key from record.
                try:
                    key = rec[self._key_field]
                except KeyError:
                    _log.critical(f"Key '{self._key_field}' not found in record: {rec}. Abort.")
                    return {}
                if not allow_dup and key in keys[i]:
                    raise ValueError(f"Duplicate key: {key}")
                keys[i].add(key)
                # Extract numeric properties.
                if has_numprops:
                    pvals = {}
                    for pkey in self._prop_deltas.keys():
                        try:
                            pvals[pkey] = float(rec[pkey])
                        except KeyError:
                            # print("@@ missing {} on {}".format(pkey, rec))
                            missing_props += 1
                            continue
                        except (TypeError, ValueError):
                            raise ValueError(
                                "Not a number: collection={c} key={k} {p}='{v}'".format(
                                    k=key, c=("old", "new")[i], p=pkey, v=rec[pkey]
                                )
                            )
                    numprops[i][key] = pvals
                # Extract properties for exact match.
                if has_eqprops:
                    try:
                        propval = tuple((p, str(rec[p])) for p in self._props)
                    except KeyError:
                        missing_props += 1
                        # print("@@ missing {} on {}".format(pkey, rec))
                        continue
                    eqprops[i][key] = propval

                # Extract informational fields.
                if has_info:
                    if key not in info:
                        info[key] = {}
                    for k in self._info:
                        info[key][k] = rec[k]

            # Stop if we don't have properties on any record at all
            if 0 < count == missing_props:
                _log.critical(f"Missing one or more properties on all {count:d} records")
                return {}
            # ..but only issue a warning for partially missing properties.
            elif missing_props > 0:
                _log.warn(f"Missing one or more properties for {missing_props:d}/{count:d} records")
        t1 = time.time()
        _log.info(f"query.end sec={t1 - t0:f}")

        # Compute missing and new keys.
        if only_values:
            missing, new = [], []
        else:
            _log.debug("compute_difference.start")
            missing, new = keys[0] - keys[1], []
            if not only_missing:
                new = keys[1] - keys[0]
            _log.debug("compute_difference.end")

        # Compute mis-matched properties.
        if has_props:
            changed = self._changed_props(
                keys,
                eqprops,
                numprops,
                info,
                has_eqprops=has_eqprops,
                has_numprops=has_numprops,
            )
        else:
            changed = []

        # Build result.
        _log.debug("build_result.begin")
        result = {}
        if not only_values:
            result[self.MISSING] = []
            for key in missing:
                rec = {self._key_field: key}
                if has_info:
                    rec.update(info.get(key, {}))
                result[self.MISSING].append(rec)
            if not only_missing:
                result[self.NEW] = []
                for key in new:
                    rec = {self._key_field: key}
                    if has_info:
                        rec.update(info.get(key, {}))
                    result[self.NEW].append(rec)
        result[self.CHANGED] = changed
        _log.debug("build_result.end")

        return result

    def _changed_props(
        self,
        keys=None,
        eqprops=None,
        numprops=None,
        info=None,
        has_numprops=False,
        has_eqprops=False,
    ):
        changed = []
        _up = lambda d, v: d.update(v) or d  # functional dict.update()
        for key in keys[0].intersection(keys[1]):
            # Numeric property comparisons.
            if has_numprops:
                for pkey in self._prop_deltas:
                    oldval, newval = numprops[0][key][pkey], numprops[1][key][pkey]
                    if self._prop_deltas[pkey].cmp(oldval, newval):
                        change = {
                            self.CHANGED_MATCH_KEY: self.CHANGED_MATCH_DELTA,
                            self._key_field: key,
                            "property": pkey,
                            self.CHANGED_OLD: f"{oldval:f}",
                            self.CHANGED_NEW: f"{newval:f}",
                            "rule": self._prop_deltas[pkey],
                            self.CHANGED_DELTA: f"{newval - oldval:f}",
                        }
                        changed.append(_up(change, info[key]) if info else change)
            # Exact property comparison.
            if has_eqprops:
                if not eqprops[0][key] == eqprops[1][key]:
                    change = {
                        self.CHANGED_MATCH_KEY: self.CHANGED_MATCH_EXACT,
                        self._key_field: key,
                        self.CHANGED_OLD: eqprops[0][key],
                        self.CHANGED_NEW: eqprops[1][key],
                    }
                    changed.append(_up(change, info[key]) if info else change)
        return changed


class Delta:
    """Delta between two properties.

    Syntax:
        +-       Change in sign, 0 not included
        +-=      Change in sign, + to 0 or - to 0 included
        +-X      abs(new - old) > X
        +X-Y     (new - old) > X or (old - new) > Y
        +-X=     abs(new - old) >= X
        +X-Y=    (new - old) >= X or (old - new) >= Y
        +X[=]   Just look in '+' direction
        -Y[=]   Just look in '-' direction
        ...%     Instead of (v2 - v1), use 100*(v2 - v1)/v1
    """

    _num = r"\d+(\.\d+)?"
    _expr = re.compile(
        "(?:"
        r"\+(?P<X>{n})?-(?P<Y>{n})?|"  # both + and -
        r"\+(?P<X2>{n})?|"  # only +
        "-(?P<Y2>{n})?"  # only -
        ")"
        "(?P<eq>=)?(?P<pct>%)?".format(n=_num)
    )

    def __init__(self, s):
        """Constructor.

        :param s: Expression string
        :type s: str
        :raises: ValueError if it doesn't match the syntax
        """
        # Match expression.
        m = self._expr.match(s)
        if m is None:
            raise ValueError(f"Bad syntax for delta '{s}'")
        if m.span()[1] != len(s):
            p = m.span()[1]
            raise ValueError(f"Junk at end of delta '{s}': {s[p:]}")

        # Save a copy of orig.
        self._orig_expr = s

        # Initialize parsed values.
        self._sign = False
        self._dx, self._dy = 0, 0
        self._pct = False  # %change
        self._eq = False  # >=,<= instead of >, <

        # Set parsed values.
        d = m.groupdict()
        # print("@@ expr :: {}".format(d))
        if all(d[k] is None for k in ("X", "Y", "X2", "Y2")):
            # Change in sign only
            self._sign = True
            self._eq = d["eq"] is not None
        elif d["X"] is not None and d["Y"] is None:
            raise ValueError(f"Missing value for negative delta '{s}'")
        else:
            if d["X2"] is not None:
                # Positive only
                self._dx = float(d["X2"])
                self._dy = None
            elif d["Y2"] is not None:
                # Negative only
                self._dx = None
                self._dy = -float(d["Y2"])
            else:
                # Both
                self._dy = -float(d["Y"])
                self._dx = float(d["X"] or d["Y"])
            self._eq = d["eq"] is not None
            self._pct = d["pct"] is not None
            # print("@@ dx,dy eq,pct = {},{}  {},{}".format(self._dx, self._dy, self._eq, self._pct))

        # Pre-calculate comparison function.
        if self._sign:
            self._cmp = self._cmp_sign
        elif self._pct:
            self._cmp = self._cmp_val_pct
        else:
            self._cmp = self._cmp_val_abs

        self._json_id = None  # for repeated serialization

    def __str__(self):
        return self._orig_expr

    def as_json(self):
        if self._json_id:
            # only serialize fully the first time
            return {"delta": {"id": self._json_id}}
        dtype = "abs" if self._eq else "pct"
        incl = self._eq
        self._json_id = next(IID)
        return {
            "delta": {
                "plus": self._dx,
                "minus": self._dy,
                "type": dtype,
                "endpoints": incl,
                "id": self._json_id,
            }
        }

    def cmp(self, old, new):
        """Compare numeric values with delta expression.

        Returns True if delta matches (is as large or larger than) this class' expression.

        Delta is computed as (new - old).

        :param old: Old value
        :type old: float
        :param new: New value
        :type new: float
        :return: True if delta between old and new is large enough, False otherwise
        :rtype: bool
        """
        return self._cmp(old, new)

    def _cmp_sign(self, a, b):
        if self._eq:
            return (a < 0 <= b) or (a > 0 >= b)
        return (a < 0 < b) or (a > 0 > b)

    def _cmp_val_abs(self, a, b):
        return self._cmp_val(b - a)

    def _cmp_val_pct(self, a, b):
        if a == 0:
            return False
        return self._cmp_val(100.0 * (b - a) / a)

    def _cmp_val(self, delta):
        oor = False  # oor = out-of-range
        if self._eq:
            if self._dx is not None:
                oor |= delta >= self._dx
            if self._dy is not None:
                oor |= delta <= self._dy
        else:
            if self._dx is not None:
                oor |= delta > self._dx
            if self._dy is not None:
                oor |= delta < self._dy
        return oor
