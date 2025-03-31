from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import print
from rich.table import Table

from .allocator import fetch_reviewers, fetch_unassigned_applications, persist_assignments, plan_assignments
from .db import db_cursor, load_sql, SCHEMA

app = typer.Typer(help="Group Scholar review load balancing CLI.")

SQL_DIR = Path(__file__).resolve().parents[3] / "sql"


@app.command("init-db")
def init_db() -> None:
    """Create schema and tables."""
    sql = load_sql(SQL_DIR / "001_init.sql")
    with db_cursor() as cursor:
        cursor.execute(sql)
    print("[green]Database initialized.[/green]")


@app.command("seed")
def seed() -> None:
    """Insert seed data into production database."""
    sql = load_sql(SQL_DIR / "seed.sql")
    with db_cursor() as cursor:
        cursor.execute(sql)
    print("[green]Seed data inserted.[/green]")


@app.command("status")
def status() -> None:
    """Show reviewer load and capacity."""
    reviewers = fetch_reviewers()
    table = Table(title="Reviewer Load Status")
    table.add_column("Reviewer")
    table.add_column("Assigned", justify="right")
    table.add_column("Capacity", justify="right")
    table.add_column("Utilization", justify="right")
    table.add_column("Expertise")

    for reviewer in reviewers:
        utilization = 0.0
        if reviewer.capacity:
            utilization = reviewer.assigned / reviewer.capacity
        table.add_row(
            reviewer.name,
            str(reviewer.assigned),
            str(reviewer.capacity),
            f"{utilization:.0%}",
            ", ".join(reviewer.tags),
        )

    print(table)


@app.command("plan")
def plan(
    limit: int | None = typer.Option(None, help="Maximum applications to assign."),
    apply: bool = typer.Option(False, help="Persist assignments."),
) -> None:
    """Plan assignments for unassigned applications."""
    reviewers = fetch_reviewers()
    applications = fetch_unassigned_applications(limit=limit)
    assignments = plan_assignments(reviewers, applications)

    if not assignments:
        print("[yellow]No assignments created.[/yellow]")
        return

    table = Table(title="Assignment Plan")
    table.add_column("Application")
    table.add_column("Reviewer")
    table.add_column("Score", justify="right")

    reviewer_lookup = {reviewer.id: reviewer for reviewer in reviewers}
    for assignment in assignments:
        reviewer = reviewer_lookup[assignment.reviewer_id]
        table.add_row(str(assignment.application_id), reviewer.name, f"{assignment.score:.2f}")

    print(table)

    if apply:
        inserted = persist_assignments(assignments)
        print(f"[green]Inserted {inserted} assignments.[/green]")


@app.command("queue")
def queue() -> None:
    """Show the unassigned application queue."""
    applications = fetch_unassigned_applications()
    table = Table(title="Unassigned Applications")
    table.add_column("ID", justify="right")
    table.add_column("Applicant")
    table.add_column("Program")
    table.add_column("Tags")
    for application in applications:
        table.add_row(
            str(application.id),
            application.applicant_name,
            application.program,
            ", ".join(application.tags),
        )
    print(table)


@app.command("snapshot")
def snapshot() -> None:
    """Show assignment coverage snapshot."""
    query = f"""
        SELECT r.name,
               COUNT(a.id) AS assigned,
               AVG(a.score) AS avg_score,
               MIN(a.assigned_at) AS first_assigned,
               MAX(a.assigned_at) AS last_assigned
          FROM {SCHEMA}.reviewers r
          LEFT JOIN {SCHEMA}.assignments a
            ON a.reviewer_id = r.id
         GROUP BY r.name
         ORDER BY r.name;
    """
    with db_cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    table = Table(title="Assignment Snapshot")
    table.add_column("Reviewer")
    table.add_column("Assigned", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("First Assigned")
    table.add_column("Last Assigned")

    for name, assigned, avg_score, first_assigned, last_assigned in rows:
        table.add_row(
            name,
            str(assigned),
            f"{(avg_score or 0):.2f}",
            str(first_assigned) if first_assigned else "-",
            str(last_assigned) if last_assigned else "-",
        )

    print(table)


@app.command("aging")
def aging(limit: int = typer.Option(10, help="Max unassigned applications to list.")) -> None:
    """Show unassigned queue age stats and oldest applications."""
    stats_query = f"""
        SELECT COUNT(*) AS unassigned_count,
               MIN(a.submitted_at) AS oldest_submitted,
               MAX(a.submitted_at) AS newest_submitted,
               AVG(EXTRACT(EPOCH FROM (NOW() - a.submitted_at))) AS avg_age_seconds
          FROM {SCHEMA}.applications a
          LEFT JOIN {SCHEMA}.assignments s
            ON s.application_id = a.id
         WHERE s.id IS NULL;
    """
    list_query = f"""
        SELECT a.id,
               a.applicant_name,
               a.program,
               a.submitted_at,
               COALESCE(a.tags, '{{}}') AS tags
          FROM {SCHEMA}.applications a
          LEFT JOIN {SCHEMA}.assignments s
            ON s.application_id = a.id
         WHERE s.id IS NULL
         ORDER BY a.submitted_at ASC
         LIMIT %s;
    """
    with db_cursor() as cursor:
        cursor.execute(stats_query)
        stats = cursor.fetchone()
        cursor.execute(list_query, (limit,))
        rows = cursor.fetchall()

    total = stats["unassigned_count"] or 0
    avg_age_seconds = stats["avg_age_seconds"] or 0
    avg_age_days = avg_age_seconds / 86400
    print(
        f"[bold]Unassigned:[/bold] {total} | "
        f"[bold]Avg Age:[/bold] {avg_age_days:.1f} days"
    )

    if not rows:
        print("[yellow]No unassigned applications.[/yellow]")
        return

    table = Table(title="Oldest Unassigned Applications")
    table.add_column("ID", justify="right")
    table.add_column("Applicant")
    table.add_column("Program")
    table.add_column("Age (days)", justify="right")
    table.add_column("Tags")

    now = datetime.now(timezone.utc)
    for row in rows:
        submitted_at = row["submitted_at"]
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)
        age_days = (now - submitted_at).total_seconds() / 86400
        table.add_row(
            str(row["id"]),
            row["applicant_name"],
            row["program"],
            f"{age_days:.1f}",
            ", ".join(row["tags"] or []),
        )

    print(table)


if __name__ == "__main__":
    app()
