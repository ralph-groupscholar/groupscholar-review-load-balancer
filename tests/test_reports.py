from datetime import datetime, timedelta, timezone

from dataclasses import dataclass

from review_load_balancer.reports import (
    BacklogAssignment,
    bucket_age,
    build_backlog_report,
    build_tag_capacity_report,
)


@dataclass(frozen=True)
class StubReviewer:
    id: int
    name: str
    capacity: int
    tags: list[str]
    assigned: int


@dataclass(frozen=True)
class StubApplication:
    id: int
    tags: list[str]


def test_bucket_age_boundaries() -> None:
    assert bucket_age(0) == "0-2"
    assert bucket_age(2.9) == "0-2"
    assert bucket_age(3) == "3-5"
    assert bucket_age(5.9) == "3-5"
    assert bucket_age(6) == "6-10"
    assert bucket_age(10.9) == "6-10"
    assert bucket_age(11) == "11+"


def test_build_backlog_report_rollup() -> None:
    now = datetime(2026, 2, 8, tzinfo=timezone.utc)
    assignments = [
        BacklogAssignment("Amina", "Maya", "STEM", now - timedelta(days=2)),
        BacklogAssignment("Amina", "Rafael", "Arts", now - timedelta(days=8)),
        BacklogAssignment("David", "Lila", "Leadership", now - timedelta(days=12)),
    ]

    report = build_backlog_report(assignments, now, stale_days=7)

    assert report.total == 3
    assert report.stale == 2
    assert report.oldest_age_days == 12
    assert report.bucket_counts == {"0-2": 1, "3-5": 0, "6-10": 1, "11+": 1}
    assert len(report.reviewer_stats) == 2
    amina_stats = next(item for item in report.reviewer_stats if item.reviewer == "Amina")
    assert amina_stats.total == 2
    assert amina_stats.stale == 1
    assert amina_stats.oldest_age_days == 8


def test_build_tag_capacity_report_rollup() -> None:
    reviewers = [
        StubReviewer(1, "Amina", 4, ["stem", "transfer"], 3),
        StubReviewer(2, "David", 2, ["transfer"], 1),
        StubReviewer(3, "Lila", 3, ["arts"], 3),
    ]
    applications = [
        StubApplication(1, ["stem"]),
        StubApplication(2, ["transfer"]),
        StubApplication(3, ["transfer"]),
        StubApplication(4, []),
    ]

    report = build_tag_capacity_report(reviewers, applications)

    transfer = next(item for item in report if item.tag == "transfer")
    assert transfer.queue_count == 2
    assert transfer.reviewer_count == 2
    assert transfer.capacity == 6
    assert transfer.assigned == 4
    assert transfer.remaining == 2
    assert transfer.coverage_ratio == 1

    untagged = next(item for item in report if item.tag == "untagged")
    assert untagged.queue_count == 1
    assert untagged.reviewer_count == 0
    assert untagged.capacity == 0
    assert untagged.remaining == 0
    assert untagged.coverage_ratio == 0
