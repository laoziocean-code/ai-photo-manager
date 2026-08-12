from src.core.scoring.scorer import WEIGHTS, compute_total, grade


def test_compute_total_full_score():
    scores = {k: 100 for k in WEIGHTS}
    assert compute_total(scores) == 100.0


def test_compute_total_clamps_overflow():
    scores = {k: 200 for k in WEIGHTS}
    assert compute_total(scores) == 100.0


def test_compute_total_missing_dim_zeroed():
    scores = {"composition": 80}
    total = compute_total(scores)
    # 仅 composition 有效，其余取 0；80*0.15 = 12
    assert total == 12.0


def test_grade_boundaries():
    assert grade(95) == "S"
    assert grade(85) == "A"
    assert grade(50) == "D"
