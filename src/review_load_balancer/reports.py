from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence


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


@dataclass(frozen=True)
class TagCapacity:
    tag: str
    queue_count: int
    reviewer_count: int
    capacity: int
    assigned: int
    remaining: int
    coverage_ratio: float | None


@dataclass(frozen=True)
class CompletedAssignment:
    reviewer: str
    program: str
    assigned_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class ThroughputReviewer:
    reviewer: str
    completed: int
    avg_cycle_days: float


@dataclass(frozen=True)
class ThroughputReport:
    total_completed: int
    avg_cycle_days: float
    min_cycle_days: float
    max_cycle_days: float
    daily_counts: dict[str, int]
    reviewer_stats: list[ThroughputReviewer]


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


def cycle_in_days(assigned_at: datetime, completed_at: datetime) -> float:
    assigned_at = _normalize_timestamp(assigned_at)
    completed_at = _normalize_timestamp(completed_at)
    return (completed_at - assigned_at).total_seconds() / 86400


def build_throughput_report(
    assignments: Iterable[CompletedAssignment],
    now: datetime,
    days: int,
) -> ThroughputReport:
    cutoff = _normalize_timestamp(now) - timedelta(days=days)
    daily_counts: dict[str, int] = {}
    reviewer_totals: dict[str, dict[str, float]] = {}
    cycles: list[float] = []

    for assignment in assignments:
        completed_at = _normalize_timestamp(assignment.completed_at)
        if completed_at < cutoff:
            continue
        cycle_days = cycle_in_days(assignment.assigned_at, completed_at)
        cycles.append(cycle_days)
        day_key = completed_at.date().isoformat()
        daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

        reviewer_stats = reviewer_totals.setdefault(
            assignment.reviewer, {"total": 0, "cycle_sum": 0.0}
        )
        reviewer_stats["total"] += 1
        reviewer_stats["cycle_sum"] += cycle_days

    total = len(cycles)
    avg_cycle = sum(cycles) / total if total else 0.0
    min_cycle = min(cycles) if cycles else 0.0
    max_cycle = max(cycles) if cycles else 0.0

    reviewer_stats_list = [
        ThroughputReviewer(
            reviewer=reviewer,
            completed=int(stats["total"]),
            avg_cycle_days=(stats["cycle_sum"] / stats["total"]) if stats["total"] else 0.0,
        )
        for reviewer, stats in reviewer_totals.items()
    ]
    reviewer_stats_list.sort(key=lambda item: item.completed, reverse=True)

    return ThroughputReport(
        total_completed=total,
        avg_cycle_days=avg_cycle,
        min_cycle_days=min_cycle,
        max_cycle_days=max_cycle,
        daily_counts=daily_counts,
        reviewer_stats=reviewer_stats_list,
    )


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


def build_tag_capacity_report(
    reviewers: Iterable[object],
    applications: Iterable[object],
    *,
    include_untagged: bool = True,
) -> list[TagCapacity]:
    demand_counts: dict[str, int] = {}
    for application in applications:
        tags = list(getattr(application, "tags", []) or [])
        if not tags:
            if include_untagged:
                demand_counts["untagged"] = demand_counts.get("untagged", 0) + 1
            continue
        for tag in tags:
            demand_counts[tag] = demand_counts.get(tag, 0) + 1

    reviewer_state: dict[str, dict[str, object]] = {}
    for index, reviewer in enumerate(reviewers):
        reviewer_tags: Sequence[str] = getattr(reviewer, "tags", []) or []
        reviewer_key = (
            getattr(reviewer, "id", None)
            or getattr(reviewer, "email", None)
            or getattr(reviewer, "name", None)
            or index
        )
        capacity = int(getattr(reviewer, "capacity", 0) or 0)
        assigned = int(getattr(reviewer, "assigned", 0) or 0)
        for tag in reviewer_tags:
            state = reviewer_state.setdefault(
                tag, {"reviewers": set(), "capacity": 0, "assigned": 0}
            )
            state["reviewers"].add(reviewer_key)
            state["capacity"] = int(state["capacity"]) + capacity
            state["assigned"] = int(state["assigned"]) + assigned

    tags = set(demand_counts) | set(reviewer_state)
    report: list[TagCapacity] = []
    for tag in tags:
        demand = demand_counts.get(tag, 0)
        state = reviewer_state.get(tag, {"reviewers": set(), "capacity": 0, "assigned": 0})
        capacity = int(state["capacity"])
        assigned = int(state["assigned"])
        remaining = max(capacity - assigned, 0)
        coverage_ratio = None
        if demand > 0:
            coverage_ratio = remaining / demand
        report.append(
            TagCapacity(
                tag=tag,
                queue_count=demand,
                reviewer_count=len(state["reviewers"]),
                capacity=capacity,
                assigned=assigned,
                remaining=remaining,
                coverage_ratio=coverage_ratio,
            )
        )

    report.sort(
        key=lambda item: (
            item.queue_count == 0,
            float("inf") if item.coverage_ratio is None else item.coverage_ratio,
            -item.queue_count,
            item.tag,
        )
    )
    return report
