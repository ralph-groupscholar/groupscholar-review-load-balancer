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
