from importlib.metadata import PackageNotFoundError
from unittest.mock import Mock

import pytest
import semver

from net_install_manager import __version__ as version_module


@pytest.mark.parametrize(
    ("package_version", "git_version", "expected"),
    [
        ("1.2.3", None, "1.2.3"),
        ("0.0.0", semver.Version(2, 0, 0), "2.0.0"),
        ("invalid", semver.Version(3, 0, 0), "3.0.0"),
        (None, semver.Version(4, 0, 0), "4.0.0"),
        (None, None, "0.0.0"),
        ("0.0.0", None, "0.0.0"),
    ],
)
def test_version_prefers_installed_metadata_then_git(
    monkeypatch, package_version, git_version, expected
):
    metadata = Mock(return_value=package_version)
    if package_version is None:
        metadata.side_effect = PackageNotFoundError("net-install-manager")
    git = Mock(return_value=git_version)
    monkeypatch.setattr(version_module, "gv", metadata)
    monkeypatch.setattr(version_module, "get_version_from_git", git)

    assert version_module._get_version() == semver.Version.parse(expected)

    metadata.assert_called_once_with("net-install-manager")
    if package_version == "1.2.3":
        git.assert_not_called()
    else:
        git.assert_called_once_with()
