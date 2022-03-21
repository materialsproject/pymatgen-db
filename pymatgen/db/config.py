"""
Database configuration functions.
Main class is DBConfig, which encapsulates a database configuration
passed in as a file or object. For example::
    cfg1 = DBConfig()  # use defaults
    cfg2 = DBConfig("/path/to/myfile.json")  # read from file
    f = open("/other/file.json")
    cfg3 = DBConfig(f)  # read from file object
    # access dict of parsed conf. settings
    settings = cfg1.settings
"""

import os

from ruamel import yaml

__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "4/25/14"

# Constants for keys
HOST_KEY = "host"
PORT_KEY = "port"
DB_KEY = "database"
COLL_KEY = "collection"
USER_KEY = "user"
PASS_KEY = "password"
ALIASES_KEY = "aliases"


class ConfigurationFileError(Exception):
    """
    Error for Config File
    """

    def __init__(self, filename, err):
        """
        Init for ConfigurationFileError.
        """
        msg = f"reading '{filename}': {err}"
        Exception.__init__(self, msg)


class DBConfig:
    """Database configuration."""

    DEFAULT_PORT = 27017
    DEFAULT_FILE = "db.json"
    ALL_SETTINGS = [
        HOST_KEY,
        PORT_KEY,
        DB_KEY,
        COLL_KEY,
        ALIASES_KEY,
    ]
    DEFAULT_SETTINGS = [
        (HOST_KEY, "localhost"),
        (PORT_KEY, DEFAULT_PORT),
        (DB_KEY, "vasp"),
        (ALIASES_KEY, {}),
    ]

    def __init__(self, config_file=None, config_dict=None):
        """
        Constructor.
        Settings are created from config_dict, if given,
        or parsed config_file, if given, otherwise
        the DEFAULT_FILE is tried and if that is not present
        the DEFAULT_SETTINGS are used without modification.
        :param config_file: Read configuration from this file.
        :type config_file: file or str path
        :param config_dict: Set configuration from this dictionary.
        :raises: ConfigurationFileError if cannot read/parse config_file
        """
        self._cfg = dict(self.DEFAULT_SETTINGS)
        settings = {}
        if config_dict:
            settings = config_dict.copy()
            auth_aliases(settings)
        else:
            # Try to use DEFAULT_FILE if no config_file
            if config_file is None:
                if os.path.exists(self.DEFAULT_FILE):
                    config_file = self.DEFAULT_FILE
            # If there was a config_file, parse it
            if config_file is not None:
                try:
                    settings = get_settings(config_file)
                except Exception as err:
                    path = _as_file(config_file).name
                    raise ConfigurationFileError(path, err)
        self._cfg.update(settings)
        normalize_auth(self._cfg)

    def __str__(self):
        return str(self._cfg)

    def copy(self):
        """Return a copy of self (internal settings are copied)."""
        return DBConfig(config_dict=self._cfg.copy())

    @property
    def settings(self):
        """
        Return settings
        """
        return self._cfg

    @property
    def host(self):
        """
        Return host
        """
        return self._cfg.get(HOST_KEY, None)

    @property
    def port(self):
        """
        Return port.
        """
        return self._cfg.get(PORT_KEY, self.DEFAULT_PORT)

    @property
    def dbname(self):
        """Name of the database."""
        return self._cfg.get(DB_KEY, None)

    @dbname.setter
    def dbname(self, value):
        """
        Set dbname.
        """
        self._cfg[DB_KEY] = value

    @property
    def collection(self):
        """
        Return collection.
        """
        return self._cfg.get(COLL_KEY, None)

    @collection.setter
    def collection(self, value):
        """
        Set collection.
        """
        self._cfg[COLL_KEY] = value

    @property
    def user(self):
        """
        Return user.
        """
        return self._cfg.get(USER_KEY, None)

    @property
    def password(self):
        """
        Return password.
        """
        return self._cfg.get(PASS_KEY, None)


def get_settings(infile):
    """Read settings from input file.
    :param infile: Input file for JSON settings.
    :type infile: file or str path
    :return: Settings parsed from file
    :rtype: dict
    """
    yml = yaml.YAML()
    settings = yml.load(_as_file(infile))
    if not hasattr(settings, "keys"):
        raise ValueError(f"Settings not found in {infile}")

    # Processing of namespaced parameters in .pmgrc.yaml.
    processed_settings = {}
    for k, v in settings.items():
        if k.startswith("PMG_DB_"):
            processed_settings[k[7:].lower()] = v
        else:
            processed_settings[k] = v
    auth_aliases(processed_settings)
    return processed_settings


def auth_aliases(d):
    """Interpret user/password aliases."""
    for alias, real in ((USER_KEY, "readonly_user"), (PASS_KEY, "readonly_password")):
        if alias in d:
            d[real] = d[alias]
            del d[alias]


def normalize_auth(settings, admin=True, readonly=True, readonly_first=False):
    """Transform the readonly/admin user and password to simple user/password,
    as expected by QueryEngine. If return value is true, then
    admin or readonly password will be in keys "user" and "password".
    :param settings: Connection settings
    :type settings: dict
    :param admin: Check for admin password
    :param readonly: Check for readonly password
    :param readonly_first: Check for readonly password before admin
    :return: Whether user/password were found
    :rtype: bool
    """
    U, P = USER_KEY, PASS_KEY
    # If user/password, un-prefixed, exists, do nothing.
    if U in settings and P in settings:
        return True

    # Set prefixes
    prefixes = []
    if readonly_first:
        if readonly:
            prefixes.append("readonly_")
        if admin:
            prefixes.append("admin_")
    else:
        if admin:
            prefixes.append("admin_")
        if readonly:
            prefixes.append("readonly_")

    # Look for first user/password matching.
    found = False
    for pfx in prefixes:
        ukey, pkey = pfx + U, pfx + P
        if ukey in settings and pkey in settings:
            settings[U] = settings[ukey]
            settings[P] = settings[pkey]
            found = True
            break

    return found


def _as_file(f, mode="r"):
    if isinstance(f, str):
        return open(f, mode)
    return f
