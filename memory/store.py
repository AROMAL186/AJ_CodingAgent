"""JSONL-backed memory for plans, failures, and fixes."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from core.models import MemoryEntry


class MemoryStore:
    """Append-only memory store with lightweight retrieval."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, entry: MemoryEntry) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), ensure_ascii=True) + "\n")

    def recent_entries(self, goal: str, limit: int) -> list[MemoryEntry]:
        if not self.path.exists():
            return []

        collected: list[MemoryEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                item = json.loads(raw)
                if item.get("goal") != goal:
                    continue
                collected.append(
                    MemoryEntry(
                        timestamp=str(item.get("timestamp", "")),
                        kind=str(item.get("kind", "")),
                        goal=str(item.get("goal", "")),
                        task_id=str(item.get("task_id", "")),
                        status=str(item.get("status", "")),
                        summary=str(item.get("summary", "")),
                        details=item.get("details", {}),
                    )
                )
        return collected[-limit:]

    def render_context(self, goal: str, limit: int) -> str:
        entries = self.recent_entries(goal=goal, limit=limit)
        if not entries:
            return "No prior memory for this goal."

        lines = []
        for entry in entries:
            detail_text = json.dumps(entry.details, ensure_ascii=True)[:600]
            lines.append(
                f"[{entry.timestamp}] kind={entry.kind} task={entry.task_id} "
                f"status={entry.status} summary={entry.summary} details={detail_text}"
            )
        return "\n".join(lines)
