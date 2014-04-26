"""
Encapsulate database configuration parsing and usage.
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'
__date__ = '4/25/14'

import json
import os

class ConfigurationFileError(Exception):
    def __init__(self, filename, err):
        msg = "reading '{}': {}".format(filename, err)
        Exception.__init__(self, msg)

class DBConfig(object):
    """Database configuration.
    """

    DEFAULT_PORT = 27017
    DEFAULT_FILE = 'db.json'
    DEFAULT_SETTINGS = [
        ("host", "localhost"),
        ("port", DEFAULT_PORT),
        ("database", "vasp")
    ]

    def __init__(self, config_file=None, config_dict=None):
        """
        Constructor.

        Settings are created from config_dict, if given,
        or parsed config_file, if given, otherwise
        the DEFAULT_FILE is tried and if that is not present
        the DEFAULT_SETTINGS are used without modification.

        :param config_file: Read configuration from this file.
        :type config_file: str, file
        :param config_dict: Set configuration from this dictionary.
        :raises: ConfigurationFileError if cannot read/parse config_file
        """
        self._cfg = dict(self.DEFAULT_SETTINGS)
        settings = {}
        if config_dict:
            settings = config_dict
        else:
            # Try to use DEFAULT_FILE if no config_file
            if config_file is None:
                if os.path.exists(self.DEFAULT_FILE):
                    config_file = self.DEFAULT_FILE
            # If there was a config_file, parse it
            if config_file is not None:
                if isinstance(config_file, str):
                    config_file = open(config_file, 'r')
                try:
                    settings = get_settings(config_file)
                except Exception, err:
                    raise ConfigurationFileError(config_file.name, err)
        self._cfg.update(settings)
        normalize_auth(self._cfg)

    @property
    def settings(self):
        return self._cfg

def get_settings(infile):
    """Read settings from input file.

    :param infile: Input file for JSON settings.
    :return: Settings
    :rtype: dict
    """
    settings = json.load(open(infile))
    # Allow some aliases
    for alias, real in (("user", "readonly_user"),
                        ("password", "readonly_password")):
        if alias in settings:
            settings[real] = settings[alias]
            del settings[alias]

    return settings

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
    U, P = "user", "password"
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
