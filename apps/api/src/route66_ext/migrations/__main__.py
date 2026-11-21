"""Alembic CLI with native and owned discovery: python -m src.route66_ext.migrations.

Run from apps/api. This is not a shortcut for stamping a bootstrap-created DB.
"""
from alembic.config import CommandLine
from .config import migration_config


def main():
    cli = CommandLine(prog='python -m src.route66_ext.migrations')
    options = cli.parser.parse_args()
    config = migration_config(options.config)
    config.cmd_opts = options
    cli.run_cmd(config, options)


if __name__ == '__main__':
    main()
