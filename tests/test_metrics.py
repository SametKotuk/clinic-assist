from eval.metrics import first_rank, recall_at_k, suggest_threshold, summarize


def test_first_rank():
    assert first_rank(["a", "b", "c"], ["c"]) == 3
    assert first_rank(["a"], ["z"]) is None


def test_recall_needs_both_sources_for_conflicts():
    assert recall_at_k(["a", "b", "x"], ["a", "b"], 3) == 1.0
    assert recall_at_k(["a", "x", "y"], ["a", "b"], 3) == 0.5


def test_summarize_mrr_and_hits():
    rows = [
        {"rank": 1, "recall": {1: 1.0, 3: 1.0, 4: 1.0}},
        {"rank": 2, "recall": {1: 0.0, 3: 1.0, 4: 1.0}},
        {"rank": None, "recall": {1: 0.0, 3: 0.0, 4: 0.0}},
    ]
    s = summarize(rows)
    assert s["hit@1"] == 1 / 3 and s["hit@3"] == 2 / 3
    assert abs(s["mrr"] - (1 + 0.5) / 3) < 1e-9


def test_threshold_overlap_detected():
    assert suggest_threshold([0.85, 0.9], [0.80])["separable"] is True
    assert suggest_threshold([0.80, 0.9], [0.85])["separable"] is False
