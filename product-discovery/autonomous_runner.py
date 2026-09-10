"""JakeAI scheduled discovery runner.

Runs the existing discovery stages end-to-end without authorizing spending,
publication, checkout, deployment, or irreversible external actions.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PD = ROOT / "product-discovery"


def run(*args: str) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def json_files(path: Path, pattern: str = "*.json") -> list[Path]:
    return sorted(path.glob(pattern)) if path.exists() else []


def main() -> int:
    generated_dirs = [
        PD / "live-signals",
        PD / "radar-output",
        PD / "radar-first-pass",
        PD / "enriched-signals",
        PD / "opportunity-clusters",
        PD / "discovery-inputs",
        PD / "discovery-blocked",
        PD / "candidates",
        PD / "run-output",
    ]
    for path in generated_dirs:
        clear_dir(path)

    run(sys.executable, str(PD / "test_opportunity_clusterer.py"))
    run(sys.executable, str(PD / "news_ingestor.py"), "40")

    signals = json_files(PD / "live-signals")
    if not signals:
        raise RuntimeError("No live signals captured; synthetic evidence is forbidden.")

    for signal in signals:
        run(sys.executable, str(PD / "opportunity_radar.py"), str(signal))

    for source in json_files(PD / "radar-output"):
        shutil.copy2(source, PD / "radar-first-pass" / source.name)

    run(sys.executable, str(PD / "evidence_enricher.py"))

    for signal in json_files(PD / "enriched-signals"):
        run(sys.executable, str(PD / "opportunity_radar.py"), str(signal))

    run(sys.executable, str(PD / "opportunity_clusterer.py"))
    run(sys.executable, str(PD / "cluster_to_discovery.py"))

    for candidate in json_files(PD / "discovery-inputs"):
        run(sys.executable, str(PD / "discovery_engine.py"), str(candidate))

    candidates = []
    for path in json_files(PD / "candidates"):
        try:
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"WARNING: could not parse {path.name}: {exc}")

    candidates.sort(key=lambda item: int(item.get("score", 0) or 0), reverse=True)

    summary = {
        "runner_version": "0.1.0",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "live_signal_count": len(signals),
        "final_radar_result_count": len(json_files(PD / "radar-output")),
        "cluster_count": len(json_files(PD / "opportunity-clusters", "cluster-*.json")),
        "discovery_input_count": len(json_files(PD / "discovery-inputs")),
        "blocked_transfer_count": len(json_files(PD / "discovery-blocked")),
        "candidate_count": len(candidates),
        "top_candidates": [
            {
                "score": item.get("score"),
                "status": item.get("status"),
                "industry": item.get("industry"),
                "proposed_skill": item.get("proposed_skill"),
                "publication_authorized": False,
                "spending_authorized": False,
            }
            for item in candidates[:10]
        ],
        "controls": {
            "autonomous_discovery": True,
            "autonomous_research": True,
            "autonomous_scoring": True,
            "autonomous_candidate_preparation": True,
            "autonomous_spending": False,
            "autonomous_publication": False,
            "autonomous_checkout_enablement": False,
            "human_approval_required_for_later_gates": True,
        },
    }

    output = PD / "run-output" / "latest-run-summary.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 72)
    print("JAKEAI AUTONOMOUS DISCOVERY RUN COMPLETE")
    print(f"Signals: {summary['live_signal_count']}")
    print(f"Clusters: {summary['cluster_count']}")
    print(f"Candidates: {summary['candidate_count']}")
    print("Publication: DISABLED")
    print("Spending: DISABLED")
    print(f"Summary: {output}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
