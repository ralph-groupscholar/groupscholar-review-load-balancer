from datetime import datetime, timedelta, timezone

from review_load_balancer.reports import BacklogAssignment, bucket_age, build_backlog_report


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
