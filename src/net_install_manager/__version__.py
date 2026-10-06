"""App version."""

from importlib.metadata import version as gv, PackageNotFoundError

import semver

from net_install_manager.utilities.version import parse_semver
from net_install_manager.utilities.version import get_version_from_git


def _get_version() -> semver.Version:
    """Return the current version of the NET Install Manager."""
    try:
        package_version = gv("net-install-manager")
        if package_version != "0.0.0" and (parsed_version := parse_semver(package_version)):
            return parsed_version
    except PackageNotFoundError:
        pass

    git_version = get_version_from_git()
    if git_version is not None:
        return git_version

    return semver.Version(0, 0, 0)


__version__ = _get_version()

__all__ = ["__version__"]
