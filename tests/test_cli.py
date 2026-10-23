import argparse
from dataclasses import replace
import logging
import runpy
from unittest.mock import Mock

import pytest

from net_install_manager import net_install_manager as cli
from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core import errors


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["list-apps"], {}),
        (["list-versions", "demo", "--reverse"], {"app_name": "demo", "reverse": True}),
        (["rollback", "demo", "v1.2.3"], {"app_name": "demo", "target_version": "v1.2.3"}),
        (["uninstall", "demo", "--yes"], {"app_name": "demo", "assume_yes": True}),
        (["self-migrate"], {}),
    ],
)
def test_register_commands_parses_arguments(argv, expected):
    parser = argparse.ArgumentParser()
    parsers = cli._register_commands(parser.add_subparsers(dest="command", required=True))

    args = parser.parse_args(argv)

    assert set(parsers) == set(cli._COMMANDS)
    assert args.command == argv[0]
    for name, value in expected.items():
        assert getattr(args, name) == value


@pytest.mark.parametrize(
    ("level", "file_enabled", "expected_level"),
    [(None, False, logging.WARNING), (None, True, logging.INFO),
     ("DEBUG", False, logging.DEBUG), ("ERROR", True, logging.ERROR)],
)
def test_configure_logging_creates_parent_and_configures_handler(
    tmp_path, monkeypatch, level, file_enabled, expected_level
):
    configure = Mock()
    monkeypatch.setattr(cli.logging, "basicConfig", configure)
    log_path = tmp_path / "logs" / "ninman.log"

    cli._configure_logging(level, str(log_path) if file_enabled else None)

    configure.assert_called_once_with(
        level=expected_level,
        filename=str(log_path.resolve()) if file_enabled else None,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    assert log_path.parent.exists() == file_enabled


def test_main_lists_empty_registry_with_global_flags_anywhere(runtime, monkeypatch, capsys):
    current = Mock(return_value=runtime)
    configure = Mock()
    monkeypatch.setattr(cli.Runtime, "current", current)
    monkeypatch.setattr(cli, "_configure_logging", configure)
    monkeypatch.setattr(
        cli.sys, "argv", ["ninman", "--log-level", "DEBUG", "list-apps", "--log-file", "app.log"]
    )

    assert cli.main() == 0

    current.assert_called_once_with(False)
    configure.assert_called_once_with("DEBUG", "app.log")
    assert capsys.readouterr().out == "Installed applications:\n"


@pytest.mark.parametrize("is_admin", [False, True])
def test_main_checks_system_privileges(runtime, monkeypatch, capsys, is_admin):
    system_runtime = replace(
        runtime, system_wide=True, platform=replace(runtime.platform, is_admin=is_admin)
    )
    current = Mock(return_value=system_runtime)
    monkeypatch.setattr(cli.Runtime, "current", current)
    monkeypatch.setattr(cli, "_configure_logging", Mock())
    monkeypatch.setattr(cli.sys, "argv", ["ninman", "--system", "list-apps"])

    assert cli.main() == (0 if is_admin else 6)

    current.assert_called_once_with(True)
    assert capsys.readouterr().out == (
        "Installed applications:\n" if is_admin else
        "Error: Administrator privileges are required for system-wide installations.\n"
    )


@pytest.mark.parametrize("stage", ["validate_arguments", "parse_arguments", "execute"])
def test_main_reports_domain_errors(runtime, monkeypatch, capsys, stage):
    command = Mock(spec=BaseCommand)
    error = errors.AppNotRegisteredError("demo", runtime.registry_path)
    getattr(command, stage).side_effect = error
    monkeypatch.setitem(cli._COMMANDS, "list-apps", command)
    def register(parsers):
        return {"list-apps": parsers.add_parser("list-apps")}

    monkeypatch.setattr(cli, "_register_commands", register)
    monkeypatch.setattr(cli.Runtime, "current", lambda _system: runtime)
    monkeypatch.setattr(cli, "_configure_logging", Mock())
    monkeypatch.setattr(cli.sys, "argv", ["ninman", "list-apps"])

    assert cli.main() == 1
    assert capsys.readouterr().out == f"{error}\n"
    if stage != "execute":
        command.execute.assert_not_called()


def test_main_propagates_unexpected_errors(runtime, monkeypatch):
    monkeypatch.setattr(cli.Runtime, "current", lambda _system: runtime)
    monkeypatch.setattr(cli, "_configure_logging", Mock())
    monkeypatch.setattr(cli.sys, "argv", ["ninman", "list-apps"])
    monkeypatch.setattr(cli._COMMANDS["list-apps"], "execute", Mock(side_effect=OSError("disk")))

    with pytest.raises(OSError, match="disk"):
        cli.main()


@pytest.mark.parametrize("argv", [[], ["unknown"], ["--log-level", "TRACE"]])
def test_main_rejects_invalid_invocations(monkeypatch, capsys, argv):
    monkeypatch.setattr(cli, "_configure_logging", Mock())
    monkeypatch.setattr(cli.sys, "argv", ["ninman", *argv])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_main_version_exits_without_initializing_runtime(monkeypatch, capsys):
    current = Mock()
    monkeypatch.setattr(cli.Runtime, "current", current)
    monkeypatch.setattr(cli.sys, "argv", ["ninman", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"{cli.__version__}\n"
    current.assert_not_called()


def test_module_entrypoint_returns_main_exit_code(runtime, monkeypatch, capsys):
    monkeypatch.setattr(cli.Runtime, "current", lambda _system: runtime)
    monkeypatch.setattr(cli.logging, "basicConfig", Mock())
    monkeypatch.setattr(cli.sys, "argv", ["ninman", "list-apps"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(cli.__file__, run_name="__main__")

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == "Installed applications:\n"
