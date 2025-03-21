from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple

from .db import db_cursor


@dataclass
class AssignmentPlan:
    application_id: int
    reviewer_id: int
    reason: str


@dataclass
class BalanceSummary:
    planned: List[AssignmentPlan]
    applications_updated: int


def _load_reviewer_loads(cursor) -> Dict[int, int]:
    cursor.execute(
        """
        SELECT reviewer_id, COUNT(*) AS active_count
        FROM assignments
        WHERE status = 'assigned'
        GROUP BY reviewer_id
        """
    )
    return {row["reviewer_id"]: row["active_count"] for row in cursor.fetchall()}


def _load_assignments(cursor) -> Dict[int, set]:
    cursor.execute("SELECT application_id, reviewer_id FROM assignments")
    assignments: Dict[int, set] = {}
    for row in cursor.fetchall():
        assignments.setdefault(row["application_id"], set()).add(row["reviewer_id"])
    return assignments


def _load_conflicts(cursor) -> set:
    cursor.execute("SELECT reviewer_id, application_id FROM conflicts")
    return {(row["reviewer_id"], row["application_id"]) for row in cursor.fetchall()}


def _load_reviewers(cursor) -> List[dict]:
    cursor.execute(
        """
        SELECT id, name, email, max_load, active, expertise_tags
        FROM reviewers
        WHERE active = TRUE
        ORDER BY name
        """
    )
    return cursor.fetchall()


def _load_pending_apps(cursor) -> List[dict]:
    cursor.execute(
        """
        SELECT id, applicant_name, program, priority, submitted_at, topic_tags, status, needs_reviews
        FROM applications
        WHERE status = 'pending'
        ORDER BY priority DESC, submitted_at ASC
        """
    )
    return cursor.fetchall()


def _count_assigned_for_app(cursor, application_id: int) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) AS assigned_count
        FROM assignments
        WHERE application_id = %s
        """,
        (application_id,),
    )
    return cursor.fetchone()["assigned_count"]


def _tag_overlap(app_tags: Iterable[str], reviewer_tags: Iterable[str]) -> int:
    return len(set(app_tags or []) & set(reviewer_tags or []))


def plan_assignments(limit: int | None = None, dry_run: bool = False) -> BalanceSummary:
    with db_cursor() as cursor:
        reviewers = _load_reviewers(cursor)
        reviewer_loads = _load_reviewer_loads(cursor)
        existing_assignments = _load_assignments(cursor)
        conflicts = _load_conflicts(cursor)
        pending_apps = _load_pending_apps(cursor)

        planned: List[AssignmentPlan] = []
        assignments_remaining = limit if limit is not None else float("inf")

        for app in pending_apps:
            if assignments_remaining <= 0:
                break

            assigned_count = _count_assigned_for_app(cursor, app["id"])
            remaining = max(app["needs_reviews"] - assigned_count, 0)
            if remaining == 0:
                continue

            app_tags = app.get("topic_tags") or []
            for _ in range(remaining):
                if assignments_remaining <= 0:
                    break

                eligible = []
                for reviewer in reviewers:
                    reviewer_id = reviewer["id"]
                    if reviewer_loads.get(reviewer_id, 0) >= reviewer["max_load"]:
                        continue
                    if (reviewer_id, app["id"]) in conflicts:
                        continue
                    if reviewer_id in existing_assignments.get(app["id"], set()):
                        continue
                    overlap = _tag_overlap(app_tags, reviewer.get("expertise_tags") or [])
                    eligible.append(
                        (
                            reviewer_loads.get(reviewer_id, 0),
                            -overlap,
                            reviewer["name"],
                            reviewer,
                            overlap,
                        )
                    )

                if not eligible:
                    break

                eligible.sort()
                _, _, _, selected, overlap = eligible[0]
                reviewer_id = selected["id"]
                planned.append(
                    AssignmentPlan(
                        application_id=app["id"],
                        reviewer_id=reviewer_id,
                        reason=f"overlap:{overlap} load:{reviewer_loads.get(reviewer_id, 0)}",
                    )
                )
                reviewer_loads[reviewer_id] = reviewer_loads.get(reviewer_id, 0) + 1
                existing_assignments.setdefault(app["id"], set()).add(reviewer_id)
                assignments_remaining -= 1

        applications_updated = 0
        if not dry_run and planned:
            for plan in planned:
                cursor.execute(
                    """
                    INSERT INTO assignments (application_id, reviewer_id, assigned_at, status)
                    VALUES (%s, %s, %s, 'assigned')
                    ON CONFLICT (application_id, reviewer_id) DO NOTHING
                    """,
                    (plan.application_id, plan.reviewer_id, datetime.utcnow()),
                )

            application_ids = {plan.application_id for plan in planned}
            for application_id in application_ids:
                assigned_count = _count_assigned_for_app(cursor, application_id)
                cursor.execute(
                    "SELECT needs_reviews FROM applications WHERE id = %s",
                    (application_id,),
                )
                needs_reviews = cursor.fetchone()["needs_reviews"]
                if assigned_count >= needs_reviews:
                    cursor.execute(
                        "UPDATE applications SET status = 'in_review' WHERE id = %s",
                        (application_id,),
                    )
                    applications_updated += 1

        return BalanceSummary(planned=planned, applications_updated=applications_updated)


def load_report() -> Tuple[List[dict], List[dict]]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT reviewers.id, reviewers.name, reviewers.email, reviewers.max_load,
                   COALESCE(active_load.active_count, 0) AS active_count
            FROM reviewers
            LEFT JOIN (
                SELECT reviewer_id, COUNT(*) AS active_count
                FROM assignments
                WHERE status = 'assigned'
                GROUP BY reviewer_id
            ) AS active_load ON active_load.reviewer_id = reviewers.id
            ORDER BY active_count DESC, reviewers.name
            """
        )
        reviewer_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM applications
            GROUP BY status
            ORDER BY status
            """
        )
        app_rows = cursor.fetchall()

    return reviewer_rows, app_rows
