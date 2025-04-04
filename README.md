# Group Scholar Review Load Balancer

Balance scholarship review assignments across reviewers while tracking load, expertise fit, and conflicts.

## Features
- Creates and seeds a production-ready PostgreSQL schema.
- Greedy load-balancing assignments that consider tag overlap and reviewer capacity.
- CLI commands for initialization, seeding, balancing, and reporting (including program coverage).

## Tech
- Python 3
- PostgreSQL (psycopg2)

## Setup

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set `DATABASE_URL` to the production database before running commands.

## CLI Usage

```bash
bin/review-load-balancer init-db
bin/review-load-balancer seed
bin/review-load-balancer status
bin/review-load-balancer plan --limit 10
bin/review-load-balancer plan --apply
bin/review-load-balancer balance
bin/review-load-balancer coverage --top 10
bin/review-load-balancer queue
bin/review-load-balancer snapshot
bin/review-load-balancer aging --limit 10
bin/review-load-balancer programs
bin/review-load-balancer backlog --stale-days 7 --limit 10
```

## Notes
- Assignments are created in `review_load_balancer.assignments`.
- Applications move to `in_review` once their required reviews are assigned.

## Tests

```bash
pytest
```
