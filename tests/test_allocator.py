from review_load_balancer.allocator import (
    AssignmentDetail,
    Reviewer,
    propose_reassignments,
    score_reviewer,
)


def test_score_reviewer_prefers_tag_match():
    reviewer = Reviewer(id=1, name="A", capacity=4, tags=["stem"], assigned=1)
    stem_app = type("App", (), {"tags": ["stem"]})
    arts_app = type("App", (), {"tags": ["arts"]})

    stem_score = score_reviewer(reviewer, stem_app)
    arts_score = score_reviewer(reviewer, arts_app)

    assert stem_score > arts_score


def test_propose_reassignments_moves_from_overloaded_to_best_fit():
    reviewers = [
        Reviewer(id=1, name="A", capacity=2, tags=["stem"], assigned=2),
        Reviewer(id=2, name="B", capacity=2, tags=["arts"], assigned=0),
        Reviewer(id=3, name="C", capacity=2, tags=["stem"], assigned=0),
    ]
    assignments = [
        AssignmentDetail(
            application_id=101,
            reviewer_id=1,
            reviewer_name="A",
            applicant_name="Applicant One",
            program="Program X",
            tags=["stem"],
        )
    ]

    plans = propose_reassignments(reviewers, assignments, threshold=0.1)

    assert len(plans) == 1
    assert plans[0].from_reviewer_id == 1
    assert plans[0].to_reviewer_id == 3


def test_propose_reassignments_empty_when_balanced():
    reviewers = [
        Reviewer(id=1, name="A", capacity=2, tags=["stem"], assigned=1),
        Reviewer(id=2, name="B", capacity=2, tags=["arts"], assigned=1),
    ]
    assignments = []

    plans = propose_reassignments(reviewers, assignments, threshold=0.2)

    assert plans == []
