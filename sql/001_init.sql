CREATE SCHEMA IF NOT EXISTS review_load_balancer;

CREATE TABLE IF NOT EXISTS review_load_balancer.reviewers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL DEFAULT 0,
    expertise_tags TEXT[] DEFAULT '{}',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_load_balancer.applications (
    id SERIAL PRIMARY KEY,
    applicant_name TEXT NOT NULL,
    program TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'submitted'
);

CREATE TABLE IF NOT EXISTS review_load_balancer.assignments (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL UNIQUE REFERENCES review_load_balancer.applications(id) ON DELETE CASCADE,
    reviewer_id INTEGER NOT NULL REFERENCES review_load_balancer.reviewers(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'assigned',
    score NUMERIC(6,4) NOT NULL DEFAULT 0,
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS assignments_reviewer_status_idx
    ON review_load_balancer.assignments (reviewer_id, status);

CREATE INDEX IF NOT EXISTS assignments_completed_at_idx
    ON review_load_balancer.assignments (completed_at)
    WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS applications_submitted_idx
    ON review_load_balancer.applications (submitted_at);
