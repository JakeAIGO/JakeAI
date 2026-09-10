"""
JakeAI Cluster -> Product Discovery Adapter
Stage 0D of the Autonomous Product Discovery Pipeline

Purpose:
Convert evidence-backed synthesized opportunity clusters into
schema-compatible inputs for the existing Product Discovery Engine.

Safety rule:
Never fabricate missing evidence or source URLs.
If provenance is missing, block the transfer instead.
"""

from __future__ import annotations

import json
import re

from pathlib import Path
from typing import Any


VERSION = "0.1.0"


def norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def key(value: Any) -> str:
    return norm(value).lower()


def unique(values):
    output = []
    seen = set()

    for value in values:
        cleaned = norm(value)

        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


def read_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_radar(
    radar_directory: Path,
):
    rows = []

    for path in radar_directory.glob(
        "*-radar.json"
    ):
        try:
            rows.append(
                read_json(path)
            )
        except Exception:
            pass

    return rows


def find_members(
    cluster,
    radar_rows,
):
    member_ids = {
        key(value)
        for value in cluster.get(
            "member_signal_ids",
            [],
        )
        if value
    }

    member_titles = {
        key(value)
        for value in cluster.get(
            "member_titles",
            [],
        )
        if value
    }

    members = []

    for row in radar_rows:
        row_id = key(
            row.get("signal_id")
        )

        original = (
            row.get("original_signal")
            or {}
        )

        row_title = key(
            row.get("title")
            or original.get("title")
        )

        if (
            row_id
            and row_id in member_ids
        ):
            members.append(row)
            continue

        if (
            row_title
            and row_title in member_titles
        ):
            members.append(row)

    return members


def collect_provenance(
    members,
):
    urls = []
    evidence = []
    buyers = []

    for row in members:

        original = (
            row.get("original_signal")
            or {}
        )

        for url in (
            row.get("source_url"),
            original.get("source_url"),
            original.get("url"),
        ):
            if url:
                urls.append(url)

        title = (
            original.get("title")
            or row.get("title")
        )

        summary = (
            original.get("summary")
            or original.get(
                "description"
            )
        )

        if title:
            evidence.append(
                f"Observed signal: {title}"
            )

        if summary:
            evidence.append(
                f"Source summary: {summary}"
            )

        buyer = original.get(
            "buyer"
        )

        if buyer:
            buyers.append(buyer)

        enrichment = (
            original.get(
                "evidence_enrichment"
            )
            or {}
        )

        for source in (
            enrichment.get("sources")
            or []
        ):

            url = source.get("url")

            if url:
                urls.append(url)

            source_title = source.get(
                "title"
            )

            if source_title:
                evidence.append(
                    "Corroborating source: "
                    + source_title
                )

    return (
        unique(urls),
        unique(evidence),
        unique(buyers),
    )


def domain_profile(
    industry: str,
    problem: str,
):
    text = key(
        industry
        + " "
        + problem
    )

    if (
        "aerospace" in text
        and any(
            term in text
            for term in (
                "casting",
                "forging",
                "supplier",
                "bottleneck",
                "capacity",
            )
        )
    ):
        return {
            "skill":
                "Aerospace Supply Bottleneck "
                "Intelligence Orchestrator",

            "buyer":
                "aerospace operations leaders; "
                "supplier quality managers; "
                "production planning leaders; "
                "supply chain leaders",

            "alternatives":
                "ERP/MRP systems, supply-chain "
                "planning suites, supplier-quality "
                "systems, spreadsheets, analyst "
                "workflows, and consulting services.",

            "gap":
                "Potential gap: continuously combine "
                "authorized production, supplier, "
                "capacity, quality, and public-market "
                "signals into a traceable bottleneck "
                "view and ranked mitigation research "
                "queue.",

            "workflow":
                "Collect authorized operational inputs "
                "and permitted public evidence; "
                "normalize supplier, capacity, quality, "
                "backlog, and production signals; "
                "detect recurring constraints; rank "
                "bottleneck risks; compare user-approved "
                "mitigation options; identify missing "
                "evidence; and produce a traceable "
                "human-review packet. Do not make "
                "autonomous supplier awards, engineering "
                "approvals, safety determinations, or "
                "contractual commitments.",

            "capabilities": [
                "Data ingestion",
                "Supplier and production signal normalization",
                "Constraint detection",
                "Risk scoring and ranking",
                "Public-source research",
                "Source traceability",
                "Human review workflow",
            ],

            "risks": [
                "Operational data may be incomplete or stale",
                "Supplier and capacity conclusions can affect consequential business decisions",
                "Public reporting may duplicate or misstate underlying events",
                "Engineering, safety, contractual, and supplier-selection decisions require qualified human review",
            ],

            "validation":
                "Test with public or user-supplied "
                "aerospace supply-chain cases. Measure "
                "whether the workflow reduces time to "
                "identify and document bottlenecks while "
                "preserving source traceability. "
                "Interview or obtain direct evidence "
                "from target operators before claiming "
                "purchase demand.",
        }

    return {
        "skill":
            f"{norm(industry) or 'Industry'} "
            "Operational Opportunity Intelligence "
            "Orchestrator",

        "buyer":
            "operations leaders; process owners; "
            "planning teams",

        "alternatives":
            "Existing planning software, spreadsheets, "
            "analyst workflows, point tools, and "
            "consulting services.",

        "gap":
            "Potential gap: combine fragmented "
            "operational evidence into a traceable, "
            "ranked decision-support workflow without "
            "replacing expert judgment.",

        "workflow":
            "Collect authorized inputs and permitted "
            "public evidence; normalize the information; "
            "detect recurring constraints; rank issues; "
            "identify missing evidence; compare "
            "user-approved response options; and produce "
            "a traceable human-review packet.",

        "capabilities": [
            "Data ingestion",
            "Evidence normalization",
            "Constraint detection",
            "Scoring and ranking",
            "Source traceability",
            "Human review workflow",
        ],

        "risks": [
            "Input data may be incomplete or stale",
            "Public evidence may be duplicated or inaccurate",
            "Consequential decisions require qualified human review",
        ],

        "validation":
            "Prototype the narrow workflow using public "
            "or user-supplied data and test whether it "
            "reduces analysis time without making "
            "consequential decisions.",
    }


def build_score_fields(
    cluster,
    urls,
    buyers,
):
    cluster_score = int(
        cluster.get(
            "cluster_score",
            0,
        )
        or 0
    )

    signal_count = int(
        cluster.get(
            "signal_count",
            0,
        )
        or 0
    )

    return {
        "pain_urgency":
            min(
                20,
                max(
                    10,
                    round(
                        cluster_score
                        * 0.19
                    ),
                ),
            ),

        "evidence_strength":
            min(
                15,
                7
                + min(
                    8,
                    len(urls),
                ),
            ),

        "buyer_clarity":
            13
            if buyers
            else 10,

        "repeatability":
            min(
                10,
                6
                + min(
                    4,
                    max(
                        0,
                        signal_count - 1,
                    ),
                ),
            ),

        "workflow_feasibility":
            12,

        "competitive_gap":
            5,

        "economic_value":
            min(
                10,
                max(
                    6,
                    round(
                        cluster_score
                        * 0.09
                    ),
                ),
            ),

        "jakeai_fit":
            5,
    }


def build_discovery_input(
    cluster,
    members,
):
    (
        urls,
        evidence,
        buyers,
    ) = collect_provenance(
        members
    )

    if (
        not urls
        or not evidence
    ):
        return (
            None,
            {
                "cluster_id":
                    cluster.get(
                        "cluster_id"
                    ),

                "status":
                    "BLOCKED_MISSING_PROVENANCE",

                "reason":
                    "Product Discovery requires "
                    "supporting evidence and source "
                    "URLs. No evidence was fabricated.",

                "source_url_count":
                    len(urls),

                "evidence_count":
                    len(evidence),
            },
        )

    industry = norm(
        cluster.get("industry")
        or "Unknown"
    )

    problem = norm(
        cluster.get(
            "problem_statement"
        )
        or
        "Operational opportunity "
        "requiring discovery"
    )

    profile = domain_profile(
        industry,
        problem,
    )

    buyer = (
        "; ".join(buyers)
        if buyers
        else profile["buyer"]
    )

    score_fields = (
        build_score_fields(
            cluster,
            urls,
            buyers,
        )
    )

    record = {
        "title":
            problem,

        "problem":
            "Multiple promoted signals indicate "
            "a recurring operational problem: "
            f"{problem}. This is a discovery "
            "hypothesis supported by the attached "
            "source trail, not a claim of proven "
            "market demand.",

        "industry":
            industry,

        "target_buyer":
            buyer,

        "evidence":
            evidence[:20],

        "source_urls":
            urls[:20],

        "existing_alternatives":
            profile["alternatives"],

        "identified_gap":
            profile["gap"],

        "proposed_skill":
            profile["skill"],

        "workflow_description":
            profile["workflow"],

        "required_capabilities":
            profile["capabilities"],

        "feasibility_notes":
            "A decision-support prototype appears "
            "feasible with existing data processing, "
            "research, scoring, and reporting "
            "capabilities. Integration depth depends "
            "on buyer-authorized data access.",

        "estimated_prototype_cost":
            0,

        "estimated_operating_cost":
            0,

        **score_fields,

        "risks":
            profile["risks"],

        "validation_experiment":
            profile["validation"],
    }

    return record, None


def main() -> int:

    cluster_directory = Path(
        "product-discovery/"
        "opportunity-clusters"
    )

    radar_directory = Path(
        "product-discovery/"
        "radar-output"
    )

    output_directory = Path(
        "product-discovery/"
        "discovery-inputs"
    )

    blocked_directory = Path(
        "product-discovery/"
        "discovery-blocked"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    blocked_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for directory in (
        output_directory,
        blocked_directory,
    ):
        for old_file in directory.glob(
            "*.json"
        ):
            old_file.unlink()

    radar_rows = load_radar(
        radar_directory
    )

    sent = 0
    blocked = 0

    for path in cluster_directory.glob(
        "cluster-*.json"
    ):
        cluster = read_json(path)

        if (
            cluster.get(
                "recommended_next_action"
            )
            !=
            "SEND_CLUSTER_TO_PRODUCT_DISCOVERY"
        ):
            continue

        members = find_members(
            cluster,
            radar_rows,
        )

        (
            discovery_input,
            block_record,
        ) = build_discovery_input(
            cluster,
            members,
        )

        cluster_id = norm(
            cluster.get(
                "cluster_id"
            )
            or path.stem
        )

        if block_record:
            output_path = (
                blocked_directory
                /
                f"{cluster_id}-blocked.json"
            )

            output_path.write_text(
                json.dumps(
                    block_record,
                    indent=2,
                ),
                encoding="utf-8",
            )

            blocked += 1

            continue

        output_path = (
            output_directory
            /
            f"{cluster_id}-discovery-input.json"
        )

        output_path.write_text(
            json.dumps(
                discovery_input,
                indent=2,
            ),
            encoding="utf-8",
        )

        sent += 1

    print("=" * 70)

    print(
        "JAKEAI CLUSTER -> "
        "PRODUCT DISCOVERY ADAPTER"
    )

    print("=" * 70)

    print(
        f"Discovery inputs created: "
        f"{sent}"
    )

    print(
        "Transfers blocked for "
        f"missing provenance: {blocked}"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
