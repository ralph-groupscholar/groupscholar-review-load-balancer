from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .db import SCHEMA, db_cursor


@dataclass(frozen=True)
class Reviewer:
    id: int
    name: str
    capacity: int
    tags: list[str]
    assigned: int


@dataclass(frozen=True)
class Application:
    id: int
    applicant_name: str
    program: str
    tags: list[str]


@dataclass(frozen=True)
class Assignment:
    application_id: int
    reviewer_id: int
    score: float


@dataclass(frozen=True)
class AssignmentDetail:
    application_id: int
    reviewer_id: int
    reviewer_name: str
    applicant_name: str
    program: str
    tags: list[str]


@dataclass(frozen=True)
class ReassignmentPlan:
    application_id: int
    from_reviewer_id: int
    from_reviewer_name: str
    to_reviewer_id: int
    to_reviewer_name: str
    score: float


def fetch_reviewers() -> list[Reviewer]:
    query = f"""
        SELECT r.id,
               r.name,
               r.capacity,
               COALESCE(r.expertise_tags, '{{}}') AS expertise_tags,
               COUNT(a.id) AS assigned
          FROM {SCHEMA}.reviewers r
          LEFT JOIN {SCHEMA}.assignments a
            ON a.reviewer_id = r.id
           AND a.status IN ('assigned', 'in_review')
         WHERE r.active = TRUE
         GROUP BY r.id
         ORDER BY r.name;
    """
    with db_cursor() as cursor:
        cursor.execute(query)
        return [
            Reviewer(
                id=row[0],
                name=row[1],
                capacity=row[2],
                tags=list(row[3] or []),
                assigned=row[4],
            )
            for row in cursor.fetchall()
        ]


def fetch_unassigned_applications(limit: int | None = None) -> list[Application]:
    limit_clause = ""
    if limit:
        limit_clause = "LIMIT %s"
    query = f"""
        SELECT a.id,
               a.applicant_name,
               a.program,
               COALESCE(a.tags, '{{}}') AS tags
          FROM {SCHEMA}.applications a
          LEFT JOIN {SCHEMA}.assignments s
            ON s.application_id = a.id
         WHERE s.id IS NULL
         ORDER BY a.submitted_at ASC
         {limit_clause};
    """
    with db_cursor() as cursor:
        if limit:
            cursor.execute(query, (limit,))
        else:
            cursor.execute(query)
        return [
            Application(
                id=row[0],
                applicant_name=row[1],
                program=row[2],
                tags=list(row[3] or []),
            )
            for row in cursor.fetchall()
        ]


def score_reviewer(reviewer: Reviewer, application: Application) -> float:
    if reviewer.capacity <= 0:
        return 0.0
    remaining = max(reviewer.capacity - reviewer.assigned, 0)
    availability = remaining / reviewer.capacity
    if not application.tags:
        tag_score = 0.0
    else:
        tag_matches = len(set(reviewer.tags) & set(application.tags))
        tag_score = tag_matches / len(application.tags)
    return round((availability * 0.65) + (tag_score * 0.35), 4)


def plan_assignments(
    reviewers: Iterable[Reviewer],
    applications: Iterable[Application],
) -> list[Assignment]:
    assignments: list[Assignment] = []
    reviewer_state = {
        reviewer.id: {
            "reviewer": reviewer,
            "assigned": reviewer.assigned,
        }
        for reviewer in reviewers
    }

    for application in applications:
        ranked: list[tuple[float, Reviewer]] = []
        for state in reviewer_state.values():
            reviewer = state["reviewer"]
            temp_reviewer = Reviewer(
                id=reviewer.id,
                name=reviewer.name,
                capacity=reviewer.capacity,
                tags=reviewer.tags,
                assigned=state["assigned"],
            )
            score = score_reviewer(temp_reviewer, application)
            ranked.append((score, temp_reviewer))
        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best_reviewer = ranked[0]
        reviewer_state[best_reviewer.id]["assigned"] += 1
        assignments.append(
            Assignment(
                application_id=application.id,
                reviewer_id=best_reviewer.id,
                score=best_score,
            )
        )

    return assignments


def persist_assignments(assignments: Iterable[Assignment]) -> int:
    rows = [
        (assignment.application_id, assignment.reviewer_id, assignment.score)
        for assignment in assignments
    ]
    if not rows:
        return 0
    query = f"""
        INSERT INTO {SCHEMA}.assignments
            (application_id, reviewer_id, status, score)
        VALUES (%s, %s, 'assigned', %s)
        ON CONFLICT (application_id) DO NOTHING;
    """
    with db_cursor() as cursor:
        cursor.executemany(query, rows)
    return len(rows)


def fetch_active_assignments() -> list[AssignmentDetail]:
    query = f"""
        SELECT s.application_id,
               s.reviewer_id,
               r.name,
               a.applicant_name,
               a.program,
               COALESCE(a.tags, '{{}}') AS tags
          FROM {SCHEMA}.assignments s
          JOIN {SCHEMA}.reviewers r
            ON r.id = s.reviewer_id
          JOIN {SCHEMA}.applications a
            ON a.id = s.application_id
         WHERE s.status IN ('assigned', 'in_review')
         ORDER BY r.name, a.submitted_at ASC;
    """
    with db_cursor() as cursor:
        cursor.execute(query)
        return [
            AssignmentDetail(
                application_id=row[0],
                reviewer_id=row[1],
                reviewer_name=row[2],
                applicant_name=row[3],
                program=row[4],
                tags=list(row[5] or []),
            )
            for row in cursor.fetchall()
        ]


def propose_reassignments(
    reviewers: Iterable[Reviewer],
    assignments: Iterable[AssignmentDetail],
    threshold: float = 0.1,
) -> list[ReassignmentPlan]:
    reviewer_lookup = {reviewer.id: reviewer for reviewer in reviewers}
    total_capacity = sum(reviewer.capacity for reviewer in reviewers if reviewer.capacity > 0)
    total_assigned = sum(reviewer.assigned for reviewer in reviewers)
    if total_capacity <= 0:
        return []

    target_utilization = total_assigned / total_capacity
    reviewer_state: dict[int, dict[str, float | Reviewer]] = {}
    for reviewer in reviewers:
        reviewer_state[reviewer.id] = {
            "reviewer": reviewer,
            "assigned": reviewer.assigned,
        }

    excess: dict[int, int] = {}
    deficit: dict[int, int] = {}
    for reviewer in reviewers:
        if reviewer.capacity <= 0:
            continue
        utilization = reviewer.assigned / reviewer.capacity
        delta = utilization - target_utilization
        target_assigned = reviewer.capacity * target_utilization
        if delta >= threshold:
            to_offload = int(round(reviewer.assigned - target_assigned))
            if to_offload > 0:
                excess[reviewer.id] = to_offload
        elif delta <= -threshold:
            to_take = int(round(target_assigned - reviewer.assigned))
            if to_take > 0:
                deficit[reviewer.id] = to_take

    if not excess or not deficit:
        return []

    under_reviewers = [reviewer_lookup[reviewer_id] for reviewer_id in deficit]

    candidates: list[tuple[float, AssignmentDetail, Reviewer]] = []
    for assignment in assignments:
        if assignment.reviewer_id not in excess:
            continue
        application = Application(
            id=assignment.application_id,
            applicant_name=assignment.applicant_name,
            program=assignment.program,
            tags=assignment.tags,
        )
        for reviewer in under_reviewers:
            temp_reviewer = Reviewer(
                id=reviewer.id,
                name=reviewer.name,
                capacity=reviewer.capacity,
                tags=reviewer.tags,
                assigned=int(reviewer_state[reviewer.id]["assigned"]),
            )
            score = score_reviewer(temp_reviewer, application)
            if score <= 0:
                continue
            candidates.append((score, assignment, reviewer))

    candidates.sort(key=lambda item: item[0], reverse=True)

    plans: list[ReassignmentPlan] = []
    for score, assignment, reviewer in candidates:
        if excess.get(assignment.reviewer_id, 0) <= 0:
            continue
        if deficit.get(reviewer.id, 0) <= 0:
            continue
        state = reviewer_state[reviewer.id]
        if int(state["assigned"]) >= reviewer.capacity:
            continue

        reviewer_state[reviewer.id]["assigned"] = int(state["assigned"]) + 1
        excess[assignment.reviewer_id] -= 1
        deficit[reviewer.id] -= 1

        plans.append(
            ReassignmentPlan(
                application_id=assignment.application_id,
                from_reviewer_id=assignment.reviewer_id,
                from_reviewer_name=assignment.reviewer_name,
                to_reviewer_id=reviewer.id,
                to_reviewer_name=reviewer.name,
                score=score,
            )
        )

        if all(value <= 0 for value in excess.values()):
            break

    return plans
