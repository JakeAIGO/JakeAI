import copy
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("development_evidence_gate.py")
spec = importlib.util.spec_from_file_location("development_evidence_gate", MODULE_PATH)
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


def baseline():
    return {
        "candidate_title": "Utility Grid Site Planning Workflow",
        "industry": "Energy Infrastructure",
        "target_buyer": "Infrastructure planners",
        "proposed_skill": "Energy Infrastructure Site Intelligence Orchestrator",
        "stage": "VALIDATION_V0_1",
        "evidence_count": 2,
        "independent_source_count": 7,
        "source_urls": [f"https://example.com/{i}" for i in range(7)],
        "supporting_evidence": ["evidence one", "evidence two"],
        "counter_evidence": [],
        "validation_score": 64,
        "disposition": "DEVELOPMENT_EVIDENCE",
        "independently_validated": False,
        "generated_at": "2026-09-10T00:00:00+00:00",
    }


def test_known_stage2_result_holds():
    result = gate.route_stage3(baseline())
    assert result["route"] == "HOLD"
    assert result["previous_validation_score"] == 64
    assert result["product_spec_eligible"] is False
    assert result["build_authorized"] is False
    assert result["publication_authorized"] is False
    assert result["spending_authorized"] is False
    assert result["human_approval_required"] is True


def test_strong_evidence_can_only_recommend_develop():
    data = baseline()
    data.update(
        {
            "validation_score": 86,
            "evidence_count": 5,
            "independent_source_count": 7,
            "counter_evidence": ["Alternative explanation reviewed"],
            "independently_validated": True,
            "disposition": "READY_FOR_INDEPENDENT_VALIDATION",
        }
    )
    result = gate.route_stage3(data)
    assert result["route"] == "DEVELOP"
    assert result["product_spec_eligible"] is True
    # DEVELOP is advisory only; all consequential permissions remain closed.
    assert result["build_authorized"] is False
    assert result["deployment_authorized"] is False
    assert result["checkout_authorized"] is False
    assert result["publication_authorized"] is False


def test_weak_rejected_evidence_rejects():
    data = baseline()
    data.update(
        {
            "validation_score": 30,
            "evidence_count": 1,
            "independent_source_count": 1,
            "disposition": "INSUFFICIENT_INDEPENDENT_EVIDENCE",
        }
    )
    result = gate.route_stage3(data)
    assert result["route"] == "REJECT"
    assert result["product_spec_eligible"] is False


def test_missing_required_field_fails_closed():
    data = baseline()
    del data["validation_score"]
    try:
        gate.route_stage3(data)
    except ValueError as exc:
        assert "validation_score" in str(exc)
    else:
        raise AssertionError("missing validation_score should fail")


def test_invalid_score_fails_closed():
    data = baseline()
    data["validation_score"] = 101
    try:
        gate.route_stage3(data)
    except ValueError as exc:
        assert "between 0 and 100" in str(exc)
    else:
        raise AssertionError("out-of-range score should fail")


def test_input_not_mutated():
    data = baseline()
    original = copy.deepcopy(data)
    gate.route_stage3(data)
    assert data == original


if __name__ == "__main__":
    tests = [
        test_known_stage2_result_holds,
        test_strong_evidence_can_only_recommend_develop,
        test_weak_rejected_evidence_rejects,
        test_missing_required_field_fails_closed,
        test_invalid_score_fails_closed,
        test_input_not_mutated,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"PASS: {len(tests)}/{len(tests)} Stage 3 gate tests")
