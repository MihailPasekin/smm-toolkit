from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Cut:
    start: float
    end: float


class CutStrategy(Protocol):
    name: str

    def plan(self, duration: float, max_duration: int) -> list[Cut]:
        ...


class FixedDurationCutStrategy:
    """V1.5 strategy. SmartCutStrategy can replace this later."""

    name = "fixed_duration"

    def plan(self, duration: float, max_duration: int) -> list[Cut]:
        if duration <= max_duration:
            return [Cut(0.0, duration)]
        cuts = []
        start = 0.0
        while start < duration:
            end = min(start + max_duration, duration)
            cuts.append(Cut(start, end))
            start = end
        return cuts
