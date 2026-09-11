from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_dependencies_are_exactly_pinned():
    lines = [line.strip() for line in read("requirements.txt").splitlines() if line.strip() and not line.startswith("#")]
    assert lines
    assert all("==" in line for line in lines)
    assert not any(">=" in line or "~=" in line for line in lines)


def test_public_errors_do_not_echo_provider_exception_text():
    source = read("main.py")
    assert 'detail=f"Stripe Error: {str(e)}"' not in source
    assert 'detail=f"Failed to retrieve checkout session: {str(e)}"' not in source
    assert 'detail=f"Extraction failed: {str(e)}"' not in source
    assert '"error": str(e)' not in source


def test_health_endpoint_is_liveness_not_dependency_health_claim():
    source = read("main.py")
    assert '@app.get("/health")' in source
    assert '"status": "alive"' in source
    assert '"status": "healthy"' not in source


def test_robotics_endpoint_is_explicitly_advisory_not_control_ready():
    source = read("main.py")
    assert 'status="advisory_only"' in source
    assert '"safety_classification": "UNVALIDATED_PHYSICAL_CONTROL_MODEL"' in source
    assert 'status="optimized"' not in source


def test_robotics_catalog_does_not_claim_solver_is_validated_control_logic():
    source = read("main.py")
    assert 'Unvalidated educational calculation' in source
    assert 'Deterministic physics calculation for 5-fingered, 22-DoF robotic hands.' not in source
