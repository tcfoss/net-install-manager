"""Options for building an application."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildOptions:
    """Options for building an application."""

    debug_mode: bool = False
    self_contained: bool = False
    runtime_identifier: str | None = None

    def to_dict(self) -> dict:
        """Convert the BuildOptions instance into a dictionary."""
        return {
            "debug_mode": self.debug_mode,
            "self_contained": self.self_contained,
            "runtime_identifier": self.runtime_identifier,
        }

    def to_cmd_args(self) -> list[str]:
        """Convert the BuildOptions instance into a list of command-line arguments."""
        args = []

        if self.debug_mode:
            args.extend(["--configuration", "Debug"])
        else:
            args.extend(["--configuration", "Release"])

        if self.self_contained:
            args.extend(["--self-contained", "true"])
            if self.runtime_identifier:
                args.extend(["-r", self.runtime_identifier])
        else:
            args.extend(["--self-contained", "false"])

        return args

    @classmethod
    def parse(cls, data: dict) -> BuildOptions:
        """Parse a dictionary into a BuildOptions instance."""

        return cls(
            debug_mode=data.get("debug_mode", False),
            self_contained=data.get("self_contained", False),
            runtime_identifier=data.get("runtime_identifier"),
        )
