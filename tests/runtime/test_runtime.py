from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from net_install_manager.runtime import (
    architecture as arch,
    operating_system as opsys,
    platform_info,
)
from net_install_manager.runtime.architecture import Architecture
from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.runtime import runtime as runtime_module
from net_install_manager.runtime.runtime import Runtime


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        ("x86_64", Architecture.X86_64),
        ("AMD64", Architecture.X86_64),
        ("aarch64", Architecture.ARM64),
        ("arm64", Architecture.ARM64),
    ],
)
def test_architecture_current_maps_supported_values(monkeypatch, machine, expected):
    monkeypatch.setattr(arch.platform, "machine", lambda: machine)

    assert Architecture.current() is expected


def test_architecture_current_rejects_unknown_machine(monkeypatch):
    monkeypatch.setattr(arch.platform, "machine", lambda: "mips")

    with pytest.raises(ValueError, match="Unsupported architecture: mips"):
        Architecture.current()


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Windows", OperatingSystem.WINDOWS),
        ("Linux", OperatingSystem.LINUX),
        ("Darwin", OperatingSystem.MACOS),
    ],
)
def test_operating_system_current_maps_supported_values(monkeypatch, system, expected):
    monkeypatch.setattr(opsys.platform, "system", lambda: system)

    assert OperatingSystem.current() is expected


def test_operating_system_current_rejects_unknown_system(monkeypatch):
    monkeypatch.setattr(opsys.platform, "system", lambda: "Plan9")

    with pytest.raises(ValueError, match="Unsupported operating system: plan9"):
        OperatingSystem.current()


@pytest.mark.parametrize(
    ("operating_system", "is_posix", "rid"),
    [
        (OperatingSystem.WINDOWS, False, "win"),
        (OperatingSystem.LINUX, True, "linux"),
        (OperatingSystem.MACOS, True, "osx"),
    ],
)
def test_operating_system_properties(operating_system, is_posix, rid):
    assert operating_system.is_posix is is_posix
    assert operating_system.rid_string == rid


@pytest.mark.parametrize(
    ("architecture", "rid"),
    [(Architecture.X86_64, "x64"), (Architecture.ARM64, "arm64")],
)
def test_architecture_rid(architecture, rid):
    assert architecture.rid_string == rid


@pytest.mark.parametrize(
    ("architecture", "expected"),
    [("x86_64", Architecture.X86_64), ("aarch64", Architecture.ARM64)],
)
def test_platform_info_current_combines_detected_values(monkeypatch, architecture, expected):
    monkeypatch.setattr(
        OperatingSystem,
        "current",
        classmethod(lambda cls: OperatingSystem.MACOS),
    )
    monkeypatch.setattr(
        Architecture,
        "current",
        classmethod(lambda cls: expected),
    )
    monkeypatch.setattr(PlatformInfo, "_get_is_admin", lambda: False)

    assert PlatformInfo.current() == PlatformInfo(OperatingSystem.MACOS, expected, False)


@pytest.mark.parametrize(("uid", "expected"), [(0, True), (1000, False)])
def test_posix_admin_detection(monkeypatch, uid, expected):
    monkeypatch.setattr(platform_info.os, "getuid", lambda: uid, raising=False)

    assert PlatformInfo._get_is_admin(OperatingSystem.LINUX) is expected


def test_windows_admin_detection(monkeypatch):
    fake_shell = SimpleNamespace(IsUserAnAdmin=lambda: 1)
    monkeypatch.setattr(
        platform_info.ctypes, "windll", SimpleNamespace(shell32=fake_shell), raising=False
    )

    assert PlatformInfo._get_is_admin(OperatingSystem.WINDOWS)


def test_windows_admin_detection_handles_api_failure(monkeypatch):
    def fail_check():
        raise OSError("unavailable")

    fake_shell = SimpleNamespace(IsUserAnAdmin=fail_check)
    monkeypatch.setattr(
        platform_info.ctypes, "windll", SimpleNamespace(shell32=fake_shell), raising=False
    )

    assert PlatformInfo._get_is_admin(OperatingSystem.WINDOWS) is False


def _runtime(os, *, env=None, system_wide=False):
    return Runtime(
        platform=PlatformInfo(os, Architecture.X86_64),
        env=env or {},
        registry_path=Path("/unused/registry.yaml"),
        home_dir=Path("/home/tester"),
        system_wide=system_wide,
    )


def test_runtime_identity_and_identifier():
    runtime = _runtime(OperatingSystem.LINUX)

    assert runtime.os is OperatingSystem.LINUX
    assert runtime.runtime_identifier == "linux-x64"


def test_runtime_current_assembles_detected_environment(monkeypatch, tmp_path):
    env = {"NINMAN_TEST": "yes"}
    platform = PlatformInfo(OperatingSystem.MACOS, Architecture.ARM64, False)
    monkeypatch.setattr(runtime_module, "os", SimpleNamespace(environ=env))
    monkeypatch.setattr(runtime_module.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(
        runtime_module,
        "PlatformInfo",
        SimpleNamespace(current=lambda: platform),
    )
    monkeypatch.setattr(
        runtime_module,
        "OperatingSystem",
        SimpleNamespace(current=lambda: OperatingSystem.MACOS),
    )
    monkeypatch.setattr(
        Runtime,
        "_get_registry_path",
        staticmethod(lambda os, env, home, system_wide: home / "registry.yaml"),
    )

    runtime = Runtime.current(system_wide=True)

    assert runtime.platform == platform
    assert runtime.env is env
    assert runtime.home_dir == tmp_path
    assert runtime.registry_path == tmp_path / "registry.yaml"
    assert runtime.system_wide is True


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, Path("/home/tester/.cache/ninman/sources")),
        ({"XDG_CACHE_HOME": "/tmp/cache"}, Path("/tmp/cache/ninman/sources")),
    ],
)
def test_posix_user_cache_root(env, expected):
    assert _runtime(OperatingSystem.LINUX, env=env).cache_root == expected


@pytest.mark.parametrize(
    ("os", "expected"),
    [
        (OperatingSystem.LINUX, Path("/var/cache/ninman/sources")),
        (
            OperatingSystem.WINDOWS,
            Path(PureWindowsPath(r"C:\ProgramData")) / "ninman" / "cache" / "sources",
        ),
    ],
)
def test_system_cache_roots(os, expected):
    assert _runtime(os, system_wide=True).cache_root == expected


def test_windows_user_cache_uses_local_app_data():
    runtime = _runtime(
        OperatingSystem.WINDOWS,
        env={"LOCALAPPDATA": r"D:\Local"},
    )

    assert (
        runtime.cache_root == Path(PureWindowsPath(r"D:\Local")) / "ninman" / "cache" / "sources"
    )


def test_registry_path_for_posix_user_and_system():
    assert Runtime._get_registry_path(
        OperatingSystem.LINUX, {}, Path("/home/tester"), False
    ) == Path("/home/tester/.config/ninman/apps.yaml")
    assert Runtime._get_registry_path(
        OperatingSystem.MACOS,
        {"XDG_CONFIG_HOME": "/tmp/config"},
        Path("/home/tester"),
        False,
    ) == Path("/tmp/config/ninman/apps.yaml")
    assert Runtime._get_registry_path(
        OperatingSystem.LINUX, {}, Path("/home/tester"), True
    ) == Path("/etc/ninman/apps.yaml")


def test_registry_path_for_windows_user_and_system():
    user_path = Runtime._get_registry_path(
        OperatingSystem.WINDOWS,
        {"LOCALAPPDATA": r"D:\Local"},
        Path("/home/tester"),
        False,
    )
    system_path = Runtime._get_registry_path(
        OperatingSystem.WINDOWS,
        {"PROGRAMDATA": r"D:\Shared"},
        Path("/home/tester"),
        True,
    )

    assert user_path == Path(PureWindowsPath(r"D:\Local")) / "ninman" / "apps.yaml"
    assert system_path == Path(PureWindowsPath(r"D:\Shared")) / "ninman" / "apps.yaml"
