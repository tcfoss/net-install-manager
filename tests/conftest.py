from pathlib import Path

import pytest

from net_install_manager.runtime.architecture import Architecture
from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.runtime.runtime import Runtime


@pytest.fixture(params=[OperatingSystem.LINUX, OperatingSystem.WINDOWS], ids=["linux", "windows"])
def runtime(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Runtime:
    """Exercise platform policy without inheriting the host's paths or environment."""
    # Windows path conversion on POSIX can produce relative paths.
    monkeypatch.chdir(tmp_path)
    return Runtime(
        platform=PlatformInfo(request.param, Architecture.X86_64),
        env={},
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )


@pytest.fixture
def native_runtime(tmp_path: Path) -> Runtime:
    """Use real OS operations while keeping every installation inside tmp_path."""
    return Runtime(
        platform=PlatformInfo.current(),
        env={},
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )
