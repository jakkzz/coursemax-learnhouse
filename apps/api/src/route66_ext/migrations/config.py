"""Explicit Alembic discovery for native revisions plus new owned revisions.

Importing this module only builds configuration; it never connects or migrates.
Historical extension implementations remain reached through their native wrappers,
so they are not loaded a second time.
"""
import os
from pathlib import Path

from alembic.config import Config


def migration_config(ini_path=None):
    api_root = Path(__file__).resolve().parents[3]
    ini = Path(ini_path).resolve() if ini_path else api_root / "alembic.ini"
    config = Config(str(ini))
    native = api_root / "migrations"
    owned = Path(__file__).resolve().parent / "versions"
    config.set_main_option("script_location", str(native))
    config.set_main_option("version_path_separator", "os")
    config.set_main_option("version_locations", os.pathsep.join(
        (str(native / "versions"), str(owned))))
    return config


__all__ = ["migration_config"]
