CREATE SCHEMA IF NOT EXISTS review_load_balancer;

SET search_path TO review_load_balancer;

CREATE TABLE IF NOT EXISTS reviewers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    max_load INTEGER NOT NULL DEFAULT 6,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    expertise_tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    applicant_name TEXT NOT NULL,
    program TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    priority INTEGER NOT NULL DEFAULT 3,
    topic_tags TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    needs_reviews INTEGER NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS assignments (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    reviewer_id INTEGER NOT NULL REFERENCES reviewers(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'assigned',
    score NUMERIC(6, 4) NOT NULL DEFAULT 0,
    UNIQUE(application_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS conflicts (
    id SERIAL PRIMARY KEY,
    reviewer_id INTEGER NOT NULL REFERENCES reviewers(id) ON DELETE CASCADE,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    UNIQUE(reviewer_id, application_id)
);

ALTER TABLE reviewers ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE reviewers ADD COLUMN IF NOT EXISTS max_load INTEGER NOT NULL DEFAULT 6;
ALTER TABLE reviewers ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE reviewers ADD COLUMN IF NOT EXISTS expertise_tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE reviewers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE applications ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE applications ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 3;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS topic_tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE applications ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE applications ADD COLUMN IF NOT EXISTS needs_reviews INTEGER NOT NULL DEFAULT 2;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'review_load_balancer'
          AND table_name = 'reviewers'
          AND column_name = 'capacity'
    ) THEN
        UPDATE review_load_balancer.reviewers
        SET max_load = capacity
        WHERE max_load IS NULL OR max_load = 0;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'review_load_balancer'
          AND table_name = 'applications'
          AND column_name = 'tags'
    ) THEN
        UPDATE review_load_balancer.applications
        SET topic_tags = tags
        WHERE topic_tags = '{}'::TEXT[];
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'review_load_balancer'
          AND table_name = 'applications'
          AND column_name = 'status'
    ) THEN
        UPDATE review_load_balancer.applications
        SET status = 'pending'
        WHERE status = 'submitted';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'assignments_application_id_key'
    ) THEN
        ALTER TABLE review_load_balancer.assignments
            DROP CONSTRAINT assignments_application_id_key;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'assignments_application_id_reviewer_id_key'
    ) THEN
        ALTER TABLE review_load_balancer.assignments
            ADD CONSTRAINT assignments_application_id_reviewer_id_key
            UNIQUE (application_id, reviewer_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_assignments_reviewer_status
    ON assignments (reviewer_id, status);

CREATE INDEX IF NOT EXISTS idx_assignments_application
    ON assignments (application_id);

CREATE INDEX IF NOT EXISTS idx_applications_status
    ON applications (status, priority DESC, submitted_at ASC);
