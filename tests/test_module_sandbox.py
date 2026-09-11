import json
from pathlib import Path

from tools.module_sandbox import protected_core_override_errors, validate_manifest

POLICY = json.loads(Path("governance/module_sandbox_policy.json").read_text())


def manifest(module_id="demo"):
    return {
        "schema_version": "1.0", "module_id": module_id, "name": "Demo", "kind": "product",
        "owner": "JakeAI", "purpose": "test", "entrypoints": [], "capabilities": [],
        "dependencies": [], "data_access": [], "network_access": "none", "secrets_required": [],
        "production_authorized": False, "publication_authorized": False, "commercial_authorized": False
    }


def test_valid_manifest_passes(tmp_path):
    d = tmp_path / "demo"; d.mkdir()
    (d / "module.json").write_text(json.dumps(manifest()), encoding="utf-8")
    assert validate_manifest(d, POLICY) == []


def test_missing_manifest_fails(tmp_path):
    d = tmp_path / "demo"; d.mkdir()
    assert any("missing module.json" in e for e in validate_manifest(d, POLICY))


def test_module_cannot_self_authorize(tmp_path):
    d = tmp_path / "demo"; d.mkdir()
    m = manifest(); m["commercial_authorized"] = True
    (d / "module.json").write_text(json.dumps(m), encoding="utf-8")
    assert any("commercial_authorized must remain false" in e for e in validate_manifest(d, POLICY))


def test_module_id_must_match_directory(tmp_path):
    d = tmp_path / "demo"; d.mkdir()
    (d / "module.json").write_text(json.dumps(manifest("other")), encoding="utf-8")
    assert any("module_id must equal directory name" in e for e in validate_manifest(d, POLICY))


def test_network_access_is_explicit(tmp_path):
    d = tmp_path / "demo"; d.mkdir()
    m = manifest(); m["network_access"] = "anything"
    (d / "module.json").write_text(json.dumps(m), encoding="utf-8")
    assert any("network_access" in e for e in validate_manifest(d, POLICY))


def test_protected_core_without_override_fails():
    errors = protected_core_override_errors(["tools/change_control.py"], ["tools/change_control.py"], POLICY)
    assert any("without an approved governed override" in e for e in errors)
