"""Read-only workspace inspection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from tools.file_manager import FileManager


@dataclass(slots=True)
class WorkspaceFileTool:
    """Builds workspace snapshots without performing mutations."""

    file_manager: FileManager

    def inventory(self) -> dict[str, list[str]]:
        return self.file_manager.inventory()

    def build_snapshot(self, max_files: int, max_chars_per_file: int) -> str:
        return self.file_manager.build_snapshot(
            max_files=max_files,
            max_chars_per_file=max_chars_per_file,
        )
