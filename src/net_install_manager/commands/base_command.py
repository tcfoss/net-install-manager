"""Base class for commands."""

from abc import ABC, abstractmethod
import argparse

from net_install_manager.runtime.runtime import Runtime


class BaseCommand[T](ABC):
    """Abstract base class for all commands."""

    @abstractmethod
    def execute(self, runtime: Runtime, args: T) -> None:
        """Execute the command."""

    @staticmethod
    @abstractmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the command with the given subparsers."""

    @staticmethod
    @abstractmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> T:
        """Parse the command-line arguments."""

    @staticmethod
    def validate_arguments(
        parser: argparse.ArgumentParser,  # pylint: disable=unused-argument
        runtime: Runtime,  # pylint: disable=unused-argument
        args: argparse.Namespace,  # pylint: disable=unused-argument
    ) -> None:
        """Validate the command-line arguments."""
