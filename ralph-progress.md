# Ralph Progress

## 2026-02-08
- Added completed-review throughput reporting with cycle-time rollups and daily totals.
- Added completion tracking to assignments schema plus a migration and seed data updates.
- Updated init-db to run ordered migrations and added tests for throughput reports.
- Documented the new throughput command in README.

## 2026-02-08
- Added backlog aging report with reviewer rollups and oldest assignment list.
- Created report helpers with tests for age bucketing and stale rollups.
- Seeded sample assignments to make backlog reporting meaningful.
- Built the review load balancer CLI with PostgreSQL-backed reviewer, application, and assignment tracking.
- Added schema + seed SQL for production data, plus status/plan/queue/snapshot commands.
- Documented setup and database usage in README.
- Added an aging report command to surface oldest unassigned applications and queue age stats.
- 2026-02-08: Built DB-backed CLI for review balancing, added schema/seed data, and ran production initialization + seeding.
- Added a programs report command to summarize per-program assignment coverage and remaining capacity.

## 2026-02-08
- Added balance and coverage CLI commands to flag utilization drift and uncovered queue tags.
- Documented new commands in README.

## 2026-02-08
- Added reassignment planning to suggest load-balancing moves based on reviewer utilization and tag fit.
- Added allocator unit tests and a dev requirements file for pytest.
- Documented the reassignment command and test setup in README.

## 2026-02-08
- Added tag capacity coverage report to compare queue demand with reviewer capacity.
- Added tag capacity reporting helper and tests, plus pytest config for import paths.
- Documented the new tag-capacity CLI command.
