from pathlib import Path, PureWindowsPath

import pytest

from net_install_manager.utilities.paths import get_winpath_env


@pytest.mark.parametrize(
    ("env", "default", "expected"),
    [
        ({"APPDATA": r"D:\Users\test\AppData"}, r"C:\fallback", r"D:\Users\test\AppData"),
        ({}, r"C:\fallback", r"C:\fallback"),
        ({}, Path(r"E:\fallback"), r"E:\fallback"),
    ],
)
def test_get_winpath_env_uses_environment_or_default(env, default, expected):
    assert get_winpath_env("APPDATA", env, default) == Path(PureWindowsPath(expected))


def test_get_winpath_env_ignores_empty_environment_value():
    assert get_winpath_env("APPDATA", {"APPDATA": ""}, r"C:\fallback") == Path(
        PureWindowsPath(r"C:\fallback")
    )
