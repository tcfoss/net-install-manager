"""Tests for the csproj_tools utility functions."""

import semver
from net_install_manager.utilities.csproj_tools import (
    get_property_from_csproj,
    get_target_framework_from_csproj,
    get_version_from_csproj,
    get_assembly_name_from_csproj,
)

SAMPLE_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <AssemblyName>CustomApp</AssemblyName>
    <PackageId>CustomApp.Package</PackageId>
    <Version>1.2.3</Version>
  </PropertyGroup>
</Project>
"""

SAMPLE_CSPROJ_NO_VERSION = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
"""


def test_get_property_from_csproj(tmp_path):
    """Test retrieving a property from a .csproj file."""
    csproj = tmp_path / "App.csproj"
    csproj.write_text(SAMPLE_CSPROJ, encoding="utf-8")

    assert get_property_from_csproj(csproj, "OutputType") == "Exe"
    assert get_property_from_csproj(csproj, "TargetFramework") == "net8.0"
    assert get_property_from_csproj(csproj, "NonExistent") is None


def test_get_target_framework(tmp_path):
    """Test retrieving the target framework from a .csproj file."""
    csproj = tmp_path / "App.csproj"
    csproj.write_text(SAMPLE_CSPROJ, encoding="utf-8")
    assert get_target_framework_from_csproj(csproj) == "net8.0"


def test_get_version_from_csproj(tmp_path):
    """Test retrieving the version from a .csproj file."""
    csproj = tmp_path / "App.csproj"
    csproj.write_text(SAMPLE_CSPROJ, encoding="utf-8")
    assert get_version_from_csproj(csproj) == semver.Version.parse("1.2.3")

    csproj2 = tmp_path / "NoVer.csproj"
    csproj2.write_text(SAMPLE_CSPROJ_NO_VERSION, encoding="utf-8")
    assert get_version_from_csproj(csproj2) is None


def test_get_assembly_name(tmp_path):
    """Test retrieving the assembly name from a .csproj file."""
    csproj = tmp_path / "App.csproj"
    csproj.write_text(SAMPLE_CSPROJ, encoding="utf-8")
    assert get_assembly_name_from_csproj(csproj) == "CustomApp"

    csproj2 = tmp_path / "FallbackName.csproj"
    csproj2.write_text(SAMPLE_CSPROJ_NO_VERSION, encoding="utf-8")
    assert get_assembly_name_from_csproj(csproj2) == "FallbackName"
