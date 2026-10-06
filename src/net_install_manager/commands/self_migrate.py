"""Command for self migration."""

import argparse
from typing import Any
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.self_migration.migrate import main as migrate_main
from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core import errors


class SelfMigrateCommand(BaseCommand):
    """Command for self migration."""

    def execute(self, runtime: Runtime, args: Any) -> None:
        status = migrate_main(runtime)
        if status != 0:
            raise errors.SelfMigrationError(status)

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        return subparsers.add_parser(
            "self-migrate", help="Update managed files to account for changes to ninman."
        )

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> Any:
        return None
