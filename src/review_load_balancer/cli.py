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


@app.command("balance")
def balance(threshold: float = typer.Option(0.1, help="Utilization delta threshold for alerts.")) -> None:
    """Show utilization balance vs overall target and capacity deltas."""
    reviewers = fetch_reviewers()
    total_capacity = sum(reviewer.capacity for reviewer in reviewers if reviewer.capacity > 0)
    total_assigned = sum(reviewer.assigned for reviewer in reviewers)

    if total_capacity <= 0:
        print("[yellow]No reviewer capacity available.[/yellow]")
        return

    target_utilization = total_assigned / total_capacity

    table = Table(title="Utilization Balance")
    table.add_column("Reviewer")
    table.add_column("Assigned", justify="right")
    table.add_column("Capacity", justify="right")
    table.add_column("Utilization", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("Action", justify="right")

    over_total = 0
    under_total = 0

    for reviewer in reviewers:
        if reviewer.capacity <= 0:
            utilization = 0.0
        else:
            utilization = reviewer.assigned / reviewer.capacity
        target_assigned = reviewer.capacity * target_utilization
        delta = utilization - target_utilization
        action = "-"
        if delta >= threshold:
            to_offload = int(round(reviewer.assigned - target_assigned))
            if to_offload > 0:
                action = f"offload {to_offload}"
                over_total += to_offload
        elif delta <= -threshold:
            to_take = int(round(target_assigned - reviewer.assigned))
            if to_take > 0:
                action = f"take {to_take}"
                under_total += to_take

        table.add_row(
            reviewer.name,
            str(reviewer.assigned),
            str(reviewer.capacity),
            f"{utilization:.0%}",
            f"{target_utilization:.0%}",
            f"{delta:+.0%}",
            action,
        )

    print(
        f"[bold]Target Utilization:[/bold] {target_utilization:.0%} | "
        f"[bold]Overload Moves:[/bold] {over_total} | "
        f"[bold]Underload Capacity:[/bold] {under_total}"
    )
    print(table)


@app.command("coverage")
def coverage(top: int = typer.Option(10, help="Top unmatched tags to show.")) -> None:
    """Show tag demand in the queue that lacks reviewer coverage."""
    reviewers = fetch_reviewers()
    applications = fetch_unassigned_applications()

    reviewer_tags = {tag for reviewer in reviewers for tag in reviewer.tags}
    tag_counts: dict[str, int] = {}
    for application in applications:
        for tag in application.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    unmatched = {tag: count for tag, count in tag_counts.items() if tag not in reviewer_tags}
    if not unmatched:
        print("[green]All queued tags are covered by reviewer expertise.[/green]")
        return

    table = Table(title="Uncovered Queue Tags")
    table.add_column("Tag")
    table.add_column("Queue Count", justify="right")

    for tag, count in sorted(unmatched.items(), key=lambda item: item[1], reverse=True)[:top]:
        table.add_row(tag, str(count))

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


@app.command("coverage")
def coverage() -> None:
    """Show per-program assignment coverage and remaining capacity."""
    program_query = f"""
        SELECT a.program,
               COUNT(*) AS total_apps,
               COUNT(s.id) AS assigned_apps,
               COUNT(*) - COUNT(s.id) AS unassigned_apps,
               AVG(EXTRACT(EPOCH FROM (NOW() - a.submitted_at))) AS avg_age_seconds
          FROM {SCHEMA}.applications a
          LEFT JOIN {SCHEMA}.assignments s
            ON s.application_id = a.id
         GROUP BY a.program
         ORDER BY unassigned_apps DESC, a.program;
    """
    capacity_query = f"""
        SELECT COALESCE(SUM(r.capacity), 0) AS total_capacity,
               COALESCE(SUM(assignments.assigned), 0) AS total_assigned
          FROM {SCHEMA}.reviewers r
          LEFT JOIN (
              SELECT reviewer_id, COUNT(*) AS assigned
                FROM {SCHEMA}.assignments
               WHERE status IN ('assigned', 'in_review')
               GROUP BY reviewer_id
          ) assignments
            ON assignments.reviewer_id = r.id
         WHERE r.active = TRUE;
    """
    with db_cursor() as cursor:
        cursor.execute(program_query)
        rows = cursor.fetchall()
        cursor.execute(capacity_query)
        capacity = cursor.fetchone()

    total_capacity = capacity["total_capacity"] or 0
    total_assigned = capacity["total_assigned"] or 0
    remaining = max(total_capacity - total_assigned, 0)
    utilization = (total_assigned / total_capacity) if total_capacity else 0

    print(
        f"[bold]Capacity:[/bold] {total_assigned}/{total_capacity} "
        f"({utilization:.0%}) | [bold]Remaining:[/bold] {remaining}"
    )

    if not rows:
        print("[yellow]No applications found.[/yellow]")
        return

    table = Table(title="Program Coverage")
    table.add_column("Program")
    table.add_column("Total", justify="right")
    table.add_column("Assigned", justify="right")
    table.add_column("Unassigned", justify="right")
    table.add_column("% Assigned", justify="right")
    table.add_column("Avg Age (days)", justify="right")

    for row in rows:
        total_apps = row["total_apps"] or 0
        assigned_apps = row["assigned_apps"] or 0
        unassigned_apps = row["unassigned_apps"] or 0
        avg_age_seconds = row["avg_age_seconds"] or 0
        avg_age_days = avg_age_seconds / 86400
        percent_assigned = (assigned_apps / total_apps) if total_apps else 0
        table.add_row(
            row["program"],
            str(total_apps),
            str(assigned_apps),
            str(unassigned_apps),
            f"{percent_assigned:.0%}",
            f"{avg_age_days:.1f}",
        )

    print(table)


if __name__ == "__main__":
    app()
