"""ninman manifest file definition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


@dataclass(frozen=True)
class NinmanManifest:
    """Representation of a ninman manifest file."""

    binary_name: str | None
    source_binary_name: str | None
    app_dir_name: str | None
    proj_path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> NinmanManifest:
        """Load and parse a manifest from a YAML file."""

        with path.open("r", encoding="utf-8") as manifest_file:
            data = yaml.safe_load(manifest_file)
        if not isinstance(data, dict):
            raise ValueError(f"Manifest at '{path}' must contain a YAML mapping.")
        return cls.parse(data)

    @classmethod
    def parse(cls, data: dict) -> NinmanManifest:
        """Parse a dictionary into a NinmanManifest instance."""

        normalized_data = {re.sub(r"[^a-zA-Z0-9]", "", key).lower(): data[key] for key in data}

        return cls(
            binary_name=normalized_data.get("binaryname"),
            source_binary_name=normalized_data.get("sourcebinaryname"),
            app_dir_name=normalized_data.get("appdirname"),
            proj_path=Path(normalized_data["projpath"]) if "projpath" in normalized_data else None,
        )
