import pytest
import semver

from net_install_manager.utilities import version


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("1.2.3", "1.2.3"),
        ("v1.2.3", "1.2.3"),
        ("V1.2.3-rc.1", "1.2.3-rc.1"),
        ("application version 2.0.0+build.5", "2.0.0+build.5"),
        ("", None),
        ("version 1.2", None),
        ("1.2.3.4", None),
        ("01.2.3", None),
        ("1.2.3-01", None),
        ("1.2.3-alpha..1", None),
    ],
)
def test_parse_semver(input_value, expected):
    parsed = version.parse_semver(input_value)

    actual = str(parsed) if parsed is not None else None
    assert actual == expected


@pytest.mark.parametrize(
    ("suffix", "command"),
    [
        (".dll", ["dotnet", "Sample.dll", "--version"]),
        (".exe", ["Sample.exe", "--version"]),
    ],
)
def test_get_version_from_binary_chooses_command(monkeypatch, tmp_path, suffix, command):
    executable = tmp_path / f"Sample{suffix}"
    executable.touch()
    calls = []

    def fake_exec(command_args, cwd=None):
        calls.append((command_args, cwd))
        return "v1.2.3\n"

    monkeypatch.setattr(version.sh, "exec_command_output", fake_exec)

    assert version.get_version_from_binary(executable) == semver.Version(1, 2, 3)
    expected_command = [
        str(tmp_path / item) if item.endswith((".dll", ".exe")) else item for item in command
    ]
    assert calls == [(expected_command, str(tmp_path))]


def test_get_version_from_binary_returns_none_for_missing_file(tmp_path):
    assert version.get_version_from_binary(tmp_path / "missing") is None


def test_get_version_from_binary_handles_command_failure(monkeypatch, tmp_path):
    executable = tmp_path / "app"
    executable.touch()

    def fail(*_args, **_kwargs):
        raise OSError("not executable")

    monkeypatch.setattr(version.sh, "exec_command_output", fail)

    assert version.get_version_from_binary(executable) is None
