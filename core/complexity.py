"""Complexity profiling for goals that require deeper planning."""

from __future__ import annotations

from dataclasses import dataclass


_HIGH_COMPLEXITY_KEYWORDS = {
    "agent",
    "autonomous",
    "distributed",
    "microservice",
    "production",
    "observability",
    "orchestrator",
    "queue",
    "database",
    "authentication",
    "authorization",
    "streaming",
    "workflow",
    "rag",
    "multi",
}
_MEDIUM_COMPLEXITY_KEYWORDS = {
    "api",
    "test",
    "cli",
    "validation",
    "integration",
    "refactor",
    "tool",
    "memory",
    "retry",
    "debug",
}


@dataclass(slots=True)
class ComplexityProfile:
    """Represents how much planning discipline a goal likely needs."""

    level: str
    score: int
    signals: list[str]
    guidance: str


def analyze_goal_complexity(goal: str, workspace_snapshot: str = "") -> ComplexityProfile:
    goal_lower = goal.lower()
    score = 0
    signals: list[str] = []

    goal_word_count = len(goal.split())
    if goal_word_count >= 30:
        score += 2
        signals.append("long_goal")
    elif goal_word_count >= 18:
        score += 1
        signals.append("detailed_goal")

    if "\n" in goal.strip():
        score += 1
        signals.append("multi_part_request")

    high_matches = sorted(keyword for keyword in _HIGH_COMPLEXITY_KEYWORDS if keyword in goal_lower)
    medium_matches = sorted(keyword for keyword in _MEDIUM_COMPLEXITY_KEYWORDS if keyword in goal_lower)

    if high_matches:
        score += min(4, len(high_matches))
        signals.extend(f"high:{keyword}" for keyword in high_matches[:4])
    if medium_matches:
        score += min(2, len(medium_matches) // 2 + 1)
        signals.extend(f"medium:{keyword}" for keyword in medium_matches[:3])

    workspace_file_count = workspace_snapshot.count("\n- ")
    if workspace_file_count >= 40:
        score += 2
        signals.append("large_workspace")
    elif workspace_file_count >= 12:
        score += 1
        signals.append("nontrivial_workspace")

    if score >= 6:
        level = "high"
        guidance = (
            "Treat this as a high-complexity task. Break work into small ordered tasks, "
            "protect existing behavior, validate incrementally, and prefer explicit intermediate checks."
        )
    elif score >= 3:
        level = "medium"
        guidance = (
            "Treat this as a medium-complexity task. Use a few focused tasks, keep changes modular, "
            "and include validation after each meaningful implementation step."
        )
    else:
        level = "low"
        guidance = (
            "Treat this as a low-complexity task. Keep the plan compact, but still include a concrete validation step."
        )

    return ComplexityProfile(level=level, score=score, signals=signals, guidance=guidance)
