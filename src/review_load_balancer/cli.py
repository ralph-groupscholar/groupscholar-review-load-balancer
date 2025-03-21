import argparse
from pathlib import Path

from .balancer import load_report, plan_assignments
from .db import run_sql

BASE_DIR = Path(__file__).resolve().parents[2]
SQL_DIR = BASE_DIR / "sql"


def _print_report() -> None:
    reviewer_rows, app_rows = load_report()
    print("Reviewer Load")
    for row in reviewer_rows:
        print(
            f"- {row['name']} ({row['email']}): {row['active_count']}/{row['max_load']} active"
        )
    print("\nApplication Status")
    for row in app_rows:
        print(f"- {row['status']}: {row['count']}")


def _init_db() -> None:
    run_sql(SQL_DIR / "schema.sql")
    print("Database schema ensured.")


def _seed_db() -> None:
    run_sql(SQL_DIR / "seed.sql")
    print("Seed data loaded.")


def _balance(args: argparse.Namespace) -> None:
    summary = plan_assignments(limit=args.limit, dry_run=args.dry_run)
    print(f"Planned assignments: {len(summary.planned)}")
    for plan in summary.planned:
        print(
            f"- application {plan.application_id} -> reviewer {plan.reviewer_id} ({plan.reason})"
        )
    if args.dry_run:
        print("Dry run enabled. No changes written.")
    else:
        print(f"Applications moved to in_review: {summary.applications_updated}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Balance scholarship review assignments across reviewers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create schema and tables in the database.")
    subparsers.add_parser("seed", help="Insert sample data into the database.")

    balance_parser = subparsers.add_parser(
        "balance", help="Assign pending applications to reviewers."
    )
    balance_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of assignments to create.",
    )
    balance_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan assignments without writing to the database.",
    )

    subparsers.add_parser("report", help="Show reviewer load and application status.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        _init_db()
    elif args.command == "seed":
        _seed_db()
    elif args.command == "balance":
        _balance(args)
    elif args.command == "report":
        _print_report()
    else:
        parser.error("Unknown command.")


if __name__ == "__main__":
    main()
