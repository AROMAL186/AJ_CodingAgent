"""Secure file system operations constrained to a project root."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any


IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    ".ruff_cache",
    ".venv",
    "venv",
}


class FileManager:
    """Sandboxed file manager for all local project mutations."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def read_file(self, path: str) -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            if not target.exists() or not target.is_file():
                return self._error(f"File does not exist: {path}")
            return self._success(target.read_text(encoding="utf-8"))
        except Exception as exc:
            return self._error(str(exc))

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return self._success(f"Wrote file: {self.relative_path(target)}")
        except Exception as exc:
            return self._error(str(exc))

    def append_file(self, path: str, content: str) -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
            target.write_text(existing + content, encoding="utf-8")
            return self._success(f"Appended file: {self.relative_path(target)}")
        except Exception as exc:
            return self._error(str(exc))

    def delete_file(self, path: str) -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            if not target.exists():
                return self._error(f"Path does not exist: {path}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return self._success(f"Deleted: {self.relative_path(target)}")
        except Exception as exc:
            return self._error(str(exc))

    def create_dir(self, path: str) -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            target.mkdir(parents=True, exist_ok=True)
            return self._success(f"Created directory: {self.relative_path(target)}")
        except Exception as exc:
            return self._error(str(exc))

    def move(self, src: str, dest: str) -> dict[str, Any]:
        try:
            source = self.resolve_path(src)
            destination = self.resolve_path(dest)
            if not source.exists():
                return self._error(f"Source path does not exist: {src}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            return self._success(
                f"Moved {self.relative_path(source)} to {self.relative_path(destination)}"
            )
        except Exception as exc:
            return self._error(str(exc))

    def list_files(self, path: str = ".") -> dict[str, Any]:
        try:
            target = self.resolve_path(path)
            if not target.exists():
                return self._error(f"Path does not exist: {path}")
            if target.is_file():
                return self._success([self.relative_path(target)])

            entries = []
            for entry in sorted(target.rglob("*")):
                if any(part in IGNORED_PARTS for part in entry.parts):
                    continue
                suffix = "/" if entry.is_dir() else ""
                entries.append(f"{self.relative_path(entry)}{suffix}")
            return self._success(entries)
        except Exception as exc:
            return self._error(str(exc))

    def inventory(self) -> dict[str, list[str]]:
        directories: list[str] = []
        files: list[str] = []
        for entry in sorted(self.root.rglob("*")):
            if any(part in IGNORED_PARTS for part in entry.parts):
                continue
            relative = self.relative_path(entry)
            if entry.is_dir():
                directories.append(relative)
            elif entry.is_file():
                files.append(relative)
        return {"directories": directories, "files": files}

    def build_snapshot(self, max_files: int, max_chars_per_file: int) -> str:
        inventory = self.inventory()
        tree_lines = ["Workspace directories:"]
        if inventory["directories"]:
            for directory in inventory["directories"][:max_files]:
                tree_lines.append(f"- {directory}/")
        else:
            tree_lines.append("(no subdirectories)")

        file_lines = ["", "Workspace files:"]
        files = inventory["files"][:max_files]
        if files:
            for file_path in files:
                file_lines.append(f"- {file_path}")
        else:
            file_lines.append("(empty workspace)")

        content_lines = ["", "File excerpts:"]
        for file_path in files:
            result = self.read_file(file_path)
            if result["status"] != "success":
                continue
            content = str(result["output"])
            excerpt = content[:max_chars_per_file]
            if len(content) > max_chars_per_file:
                excerpt += "\n...<truncated>"
            content_lines.append(f"### {file_path}")
            content_lines.append(excerpt if excerpt else "(empty file)")
            content_lines.append("")

        return "\n".join(tree_lines + file_lines + content_lines)

    def resolve_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        target = (self.root / candidate).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError(f"Path escapes project root: {relative_path}")
        return target

    def relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    @staticmethod
    def _success(output: Any) -> dict[str, Any]:
        return {"status": "success", "output": output, "error": None}

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"status": "error", "output": None, "error": message}
