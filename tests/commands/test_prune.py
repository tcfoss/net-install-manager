import argparse
from dataclasses import replace
from pathlib import Path
import shutil

import pytest
import semver

from net_install_manager.commands import prune
from net_install_manager.commands.prune import PruneArguments, PruneCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import Paths, get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


def _runtime(tmp_path: Path) -> Runtime:
    return replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )


def _app(tmp_path: Path) -> AppInfo:
    return AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=tmp_path / ".local" / "lib" / "Sample",
        installed_version=semver.Version(3, 0, 0),
        app_source=BuiltAppSource(tmp_path / "build"),
    )


def _install_versions(tmp_path: Path, monkeypatch) -> tuple[Runtime, Paths, list]:
    runtime = _runtime(tmp_path)
    app = _app(tmp_path)
    paths = get_paths_from_app_info(runtime, app)
    for version in ("1.0.0", "2.0.0", "3.0.0"):
        (paths.versions_dir / version).mkdir(parents=True)
    paths.current_dir.symlink_to(paths.versions_dir / "3.0.0", target_is_directory=True)
    Registry(runtime).set(app.binary_name, app)
    calls: list = []

    class TestOsOps:
        @staticmethod
        def update_current_link(
            versions_dir: Path, target_version: str, current_dir: Path
        ) -> Path:
            calls.append(("switch", target_version))
            current_dir.unlink()
            current_dir.symlink_to(versions_dir / target_version, target_is_directory=True)
            return current_dir

    monkeypatch.setattr(prune, "get_os_ops", lambda _os: TestOsOps)
    return runtime, paths, calls


def _fail_input(_prompt: str) -> str:
    raise AssertionError("unexpected confirmation prompt")


def test_prune_switches_current_before_deleting_active_version(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    app = _app(tmp_path)
    paths = get_paths_from_app_info(runtime, app)
    versions = [semver.Version(1, 0, 0), semver.Version(2, 0, 0), semver.Version(3, 0, 0)]
    for version in versions:
        (paths.versions_dir / str(version)).mkdir(parents=True)
    paths.current_dir.symlink_to(paths.versions_dir / "3.0.0", target_is_directory=True)

    registry = Registry(runtime)
    registry.set(app.binary_name, app)
    calls = []
    monkeypatch.setattr("builtins.input", _fail_input)

    class TestOsOps:
        @staticmethod
        def update_current_link(
            versions_dir: Path, target_version: str, current_dir: Path
        ) -> Path:
            calls.append(("switch", target_version))
            current_dir.unlink()
            current_dir.symlink_to(versions_dir / target_version, target_is_directory=True)
            return current_dir

    monkeypatch.setattr(prune, "get_os_ops", lambda _os: TestOsOps)
    remove_directory = shutil.rmtree

    def assert_switched_before_remove(path: str | Path) -> None:
        assert paths.current_dir.resolve() == paths.versions_dir / "2.0.0"
        assert (paths.versions_dir / "3.0.0").is_dir()
        calls.append(("remove", Path(path).name))
        remove_directory(path)

    monkeypatch.setattr(prune.shutil, "rmtree", assert_switched_before_remove)

    PruneCommand().execute(
        runtime,
        PruneArguments("sample", max_version=semver.Version(2, 0, 0), assume_yes=True),
    )

    assert calls == [("switch", "2.0.0"), ("remove", "3.0.0")]
    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(2, 0, 0)
    assert paths.current_dir.resolve() == paths.versions_dir / "2.0.0"
    assert not (paths.versions_dir / "3.0.0").exists()


def test_prune_errors_when_registered_app_has_no_versions(tmp_path, caplog):
    runtime = _runtime(tmp_path)
    app = _app(tmp_path)
    paths = get_paths_from_app_info(runtime, app)
    paths.versions_dir.mkdir(parents=True)
    Registry(runtime).set(app.binary_name, app)

    with pytest.raises(errors.NoVersionsInstalledError):
        PruneCommand().execute(runtime, PruneArguments("sample", keep_latest=1))

    assert "no installed versions" in caplog.text.lower()
    assert Registry(runtime).get("sample") == app


def test_prune_uses_min_version_to_remove_older_versions(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)

    PruneCommand().execute(
        runtime,
        PruneArguments("sample", min_version=semver.Version(2, 0, 0)),
    )

    assert not (paths.versions_dir / "1.0.0").exists()
    assert (paths.versions_dir / "2.0.0").is_dir()
    assert (paths.versions_dir / "3.0.0").is_dir()
    assert paths.current_dir.resolve() == paths.versions_dir / "3.0.0"
    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert not calls


def test_prune_rejects_removing_all_versions_without_changes(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)

    with pytest.raises(errors.PruneAllError):
        PruneCommand().execute(
            runtime,
            PruneArguments("sample", min_version=semver.Version(4, 0, 0)),
        )

    assert all((paths.versions_dir / version).is_dir() for version in ("1.0.0", "2.0.0", "3.0.0"))
    assert paths.current_dir.resolve() == paths.versions_dir / "3.0.0"
    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert not calls


@pytest.mark.parametrize(
    ("cli_args", "message"),
    [
        (["--keep-latest", "0"], "keep_latest must be a positive integer"),
        (["--min-version", "invalid"], "min_version must be a valid semantic version"),
        (["--max-version", "invalid"], "max_version must be a valid semantic version"),
        (
            ["--min-version", "3.0.0", "--max-version", "2.0.0"],
            "min_version cannot be greater than max_version",
        ),
        (
            ["--keep-latest", "1", "--min-version", "1.0.0"],
            "Cannot specify both version range and keep-latest",
        ),
        ([], "At least one pruning criterion must be specified"),
    ],
)
def test_prune_validate_arguments_rejects_invalid_combinations(cli_args, message, capsys):
    root_parser = argparse.ArgumentParser()
    prune_parser = PruneCommand.register_command(root_parser.add_subparsers())
    namespace = root_parser.parse_args(["prune", "sample", *cli_args])

    with pytest.raises(SystemExit) as exc_info:
        PruneCommand.validate_arguments(prune_parser, Runtime.current(), namespace)

    assert exc_info.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    "cli_args",
    [
        ["--keep-latest", "1"],
        ["--min-version", "1.0.0"],
        ["--max-version", "3.0.0"],
        ["--min-version", "1.0.0", "--max-version", "3.0.0"],
    ],
)
def test_prune_validate_arguments_accepts_valid_criteria(cli_args):
    root_parser = argparse.ArgumentParser()
    prune_parser = PruneCommand.register_command(root_parser.add_subparsers())
    namespace = root_parser.parse_args(["prune", "sample", *cli_args])

    assert PruneCommand.validate_arguments(prune_parser, Runtime.current(), namespace) is None


@pytest.mark.parametrize("answer", ["y", "YES", " y "])
def test_prune_proceeds_when_user_confirms_removing_current(tmp_path, monkeypatch, answer):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or answer)

    PruneCommand().execute(runtime, PruneArguments("sample", max_version=semver.Version(2, 0, 0)))

    assert len(prompts) == 1
    assert "3.0.0" in prompts[0] and "2.0.0" in prompts[0]
    assert calls == [("switch", "2.0.0")]
    assert not (paths.versions_dir / "3.0.0").exists()


def _raise_eof(_prompt: str) -> str:
    raise EOFError


@pytest.mark.parametrize("respond", [lambda _prompt: "n", lambda _prompt: "", _raise_eof])
def test_prune_cancels_without_changes_when_user_declines(tmp_path, monkeypatch, respond):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", respond)

    PruneCommand().execute(runtime, PruneArguments("sample", max_version=semver.Version(2, 0, 0)))

    assert not calls
    assert (paths.versions_dir / "3.0.0").is_dir()
    assert paths.current_dir.resolve() == paths.versions_dir / "3.0.0"
    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)


def test_prune_does_not_prompt_when_current_is_kept(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", _fail_input)

    PruneCommand().execute(runtime, PruneArguments("sample", keep_latest=2))

    assert not calls
    assert not (paths.versions_dir / "1.0.0").exists()
    assert (paths.versions_dir / "3.0.0").is_dir()


@pytest.mark.parametrize(("flags", "expected"), [([], False), (["-y"], True), (["--yes"], True)])
def test_prune_command_parses_assume_yes(flags, expected):
    parser = argparse.ArgumentParser()
    PruneCommand.register_command(parser.add_subparsers())

    namespace = parser.parse_args(["prune", "sample", "--keep-latest", "1", *flags])

    assert PruneCommand.parse_arguments(Runtime.current(), namespace).assume_yes is expected
