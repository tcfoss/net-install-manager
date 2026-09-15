"""Tests for the version_tools utility functions."""

import pytest
import semver
from net_install_manager.utilities.version_tools import (
    parse_semver,
    resolve_version,
)


def test_parse_semver():
    """Test parsing semantic version strings."""
    assert parse_semver("1.2.3") == semver.Version.parse("1.2.3")
    assert parse_semver("v2.0.1") == semver.Version.parse("2.0.1")
    assert parse_semver("V3.4.5-beta.1") == semver.Version.parse("3.4.5-beta.1")
    assert parse_semver("release-1.0.0") == semver.Version.parse("1.0.0")
    assert parse_semver("invalid") is None
    assert parse_semver("") is None
    assert parse_semver("v") is None
    assert parse_semver("V") is None
    assert parse_semver("1.2.3.4") is None


def test_resolve_version_explicit():
    """Test resolving an explicitly specified version."""
    v = resolve_version(explicit_version="2.5.0")
    assert v == semver.Version.parse("2.5.0")


def test_resolve_version_from_csproj(tmp_path):
    """Test resolving the version from a .csproj file."""
    csproj = tmp_path / "App.csproj"
    csproj.write_text(
        """<Project><PropertyGroup><Version>3.1.4</Version></PropertyGroup></Project>""",
        encoding="utf-8",
    )
    v = resolve_version(csproj_path=csproj)
    assert v == semver.Version.parse("3.1.4")


def test_resolve_version_fails_when_unresolvable(tmp_path):
    """Test that resolving the version fails when it cannot be determined."""
    with pytest.raises(ValueError, match="determine application version"):
        resolve_version(csproj_path=tmp_path / "Nonexistent.csproj")
