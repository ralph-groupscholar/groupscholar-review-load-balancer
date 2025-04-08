ALTER TABLE review_load_balancer.assignments
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS assignments_completed_at_idx
    ON review_load_balancer.assignments (completed_at)
    WHERE status = 'completed';
