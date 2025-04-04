from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class BacklogAssignment:
    reviewer: str
    applicant: str
    program: str
    assigned_at: datetime


@dataclass(frozen=True)
class ReviewerBacklog:
    reviewer: str
    total: int
    stale: int
    oldest_age_days: float


@dataclass(frozen=True)
class BacklogReport:
    total: int
    stale: int
    avg_age_days: float
    oldest_age_days: float
    bucket_counts: dict[str, int]
    reviewer_stats: list[ReviewerBacklog]
    oldest_assignments: list[tuple[BacklogAssignment, float]]


def _normalize_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def age_in_days(assigned_at: datetime, now: datetime) -> float:
    assigned_at = _normalize_timestamp(assigned_at)
    now = _normalize_timestamp(now)
    return (now - assigned_at).total_seconds() / 86400


def bucket_age(age_days: float) -> str:
    if age_days < 3:
        return "0-2"
    if age_days < 6:
        return "3-5"
    if age_days < 11:
        return "6-10"
    return "11+"


def build_backlog_report(
    assignments: Iterable[BacklogAssignment],
    now: datetime,
    stale_days: int,
) -> BacklogReport:
    bucket_counts = {"0-2": 0, "3-5": 0, "6-10": 0, "11+": 0}
    reviewer_totals: dict[str, dict[str, float]] = {}
    oldest_assignments: list[tuple[BacklogAssignment, float]] = []
    ages: list[float] = []
    stale = 0

    for assignment in assignments:
        age_days = age_in_days(assignment.assigned_at, now)
        ages.append(age_days)
        bucket_counts[bucket_age(age_days)] += 1
        oldest_assignments.append((assignment, age_days))

        reviewer_stats = reviewer_totals.setdefault(
            assignment.reviewer, {"total": 0, "stale": 0, "oldest": 0.0}
        )
        reviewer_stats["total"] += 1
        if age_days >= stale_days:
            reviewer_stats["stale"] += 1
            stale += 1
        reviewer_stats["oldest"] = max(reviewer_stats["oldest"], age_days)

    total = len(ages)
    avg_age = sum(ages) / total if total else 0.0
    oldest = max(ages) if ages else 0.0

    reviewer_stats_list = [
        ReviewerBacklog(
            reviewer=reviewer,
            total=int(stats["total"]),
            stale=int(stats["stale"]),
            oldest_age_days=float(stats["oldest"]),
        )
        for reviewer, stats in reviewer_totals.items()
    ]
    reviewer_stats_list.sort(key=lambda item: (item.stale, item.total), reverse=True)

    oldest_assignments.sort(key=lambda item: item[1], reverse=True)

    return BacklogReport(
        total=total,
        stale=stale,
        avg_age_days=avg_age,
        oldest_age_days=oldest,
        bucket_counts=bucket_counts,
        reviewer_stats=reviewer_stats_list,
        oldest_assignments=oldest_assignments,
    )
