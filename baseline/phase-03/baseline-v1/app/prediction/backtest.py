"""預測準確率回測（REQ_009）：方向準確率與幅度區間命中率統計。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestRecord:
    predicted_direction: str
    range_lower_pct: float
    range_upper_pct: float
    actual_return_pct: float

    @property
    def actual_direction(self) -> str:
        if self.actual_return_pct > 1.0:
            return "UP"
        if self.actual_return_pct < -1.0:
            return "DOWN"
        return "FLAT"

    @property
    def direction_hit(self) -> bool:
        return self.predicted_direction == self.actual_direction

    @property
    def range_hit(self) -> bool:
        return self.range_lower_pct <= self.actual_return_pct <= self.range_upper_pct


@dataclass(frozen=True)
class BacktestSummary:
    window_weeks: int
    directional_accuracy: float
    range_hit_rate: float


def summarize(records: list[BacktestRecord]) -> BacktestSummary:
    if not records:
        raise ValueError("回測記錄不可為空，至少需累積 1 筆已知結果之預測")

    direction_hits = sum(1 for r in records if r.direction_hit)
    range_hits = sum(1 for r in records if r.range_hit)
    n = len(records)

    return BacktestSummary(
        window_weeks=n,
        directional_accuracy=round(direction_hits / n, 3),
        range_hit_rate=round(range_hits / n, 3),
    )
