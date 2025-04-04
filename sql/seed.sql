INSERT INTO review_load_balancer.reviewers (name, email, capacity, expertise_tags, active)
VALUES
    ('Amina Lewis', 'amina.lewis@groupscholar.com', 12, ARRAY['stem', 'first-gen', 'research'], TRUE),
    ('David Chen', 'david.chen@groupscholar.com', 10, ARRAY['arts', 'portfolio', 'community'], TRUE),
    ('Sofia Ramirez', 'sofia.ramirez@groupscholar.com', 8, ARRAY['leadership', 'service', 'essay'], TRUE),
    ('Noah Patel', 'noah.patel@groupscholar.com', 9, ARRAY['business', 'finance', 'startup'], TRUE),
    ('Grace Okafor', 'grace.okafor@groupscholar.com', 11, ARRAY['health', 'science', 'impact'], TRUE)
ON CONFLICT (email) DO NOTHING;

INSERT INTO review_load_balancer.applications (applicant_name, program, tags, submitted_at, status)
VALUES
    ('Maya Rivera', 'STEM Scholars', ARRAY['stem', 'research', 'first-gen'], NOW() - INTERVAL '5 days', 'submitted'),
    ('Ethan Brooks', 'Creative Futures', ARRAY['arts', 'portfolio', 'community'], NOW() - INTERVAL '4 days', 'submitted'),
    ('Lila Nguyen', 'Leadership Fellows', ARRAY['leadership', 'service', 'essay'], NOW() - INTERVAL '4 days', 'submitted'),
    ('Zion Carter', 'Entrepreneur Track', ARRAY['business', 'startup', 'finance'], NOW() - INTERVAL '3 days', 'submitted'),
    ('Amara Singh', 'Health Impact', ARRAY['health', 'science', 'impact'], NOW() - INTERVAL '3 days', 'submitted'),
    ('Olivia Park', 'STEM Scholars', ARRAY['stem', 'impact'], NOW() - INTERVAL '2 days', 'submitted'),
    ('Rafael Torres', 'Creative Futures', ARRAY['arts', 'community'], NOW() - INTERVAL '2 days', 'submitted'),
    ('Jada Stewart', 'Leadership Fellows', ARRAY['leadership', 'essay'], NOW() - INTERVAL '1 day', 'submitted'),
    ('Leo Kim', 'Entrepreneur Track', ARRAY['business', 'finance'], NOW() - INTERVAL '1 day', 'submitted')
ON CONFLICT DO NOTHING;

INSERT INTO review_load_balancer.assignments (application_id, reviewer_id, status, score, assigned_at)
SELECT app.id, reviewer.id, 'assigned', 0.92, NOW() - INTERVAL '6 days'
  FROM review_load_balancer.applications app
  JOIN review_load_balancer.reviewers reviewer
    ON reviewer.email = 'amina.lewis@groupscholar.com'
 WHERE app.applicant_name = 'Maya Rivera'
ON CONFLICT (application_id) DO NOTHING;

INSERT INTO review_load_balancer.assignments (application_id, reviewer_id, status, score, assigned_at)
SELECT app.id, reviewer.id, 'in_review', 0.87, NOW() - INTERVAL '8 days'
  FROM review_load_balancer.applications app
  JOIN review_load_balancer.reviewers reviewer
    ON reviewer.email = 'david.chen@groupscholar.com'
 WHERE app.applicant_name = 'Ethan Brooks'
ON CONFLICT (application_id) DO NOTHING;

INSERT INTO review_load_balancer.assignments (application_id, reviewer_id, status, score, assigned_at)
SELECT app.id, reviewer.id, 'assigned', 0.89, NOW() - INTERVAL '3 days'
  FROM review_load_balancer.applications app
  JOIN review_load_balancer.reviewers reviewer
    ON reviewer.email = 'sofia.ramirez@groupscholar.com'
 WHERE app.applicant_name = 'Lila Nguyen'
ON CONFLICT (application_id) DO NOTHING;
