"""Entrypoint for migration scripts."""

import logging

import semver

from net_install_manager.__version__ import __version__
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


def _get_last_version(runtime: Runtime) -> semver.Version:
    """Return the version last used to save the registry."""

    registry = Registry(runtime)
    return registry.version


def main(runtime: Runtime) -> int:
    """Main entry point for migration scripts."""

    try:
        last_version = _get_last_version(runtime)
        logging.info("Last registry version: %s", last_version)
    except Exception as e:  # pylint: disable=broad-except
        logging.warning("Failed to retrieve last registry version: %s", e)
        last_version = semver.Version(0, 0, 0)

    if last_version < semver.Version(0, 2, 0):
        import net_install_manager.self_migration.mod_0_2_0_upgrade_registry as m  # pylint: disable=import-outside-toplevel

        val = m.main(runtime)
        if val != 0:
            return val

    return 0
