"""
JakeAI Opportunity Clusterer
Stage 0C of the Autonomous Product Discovery Pipeline

Purpose:
Cluster promoted Radar results that describe the same underlying
commercial/operational problem so multiple headlines do not become
duplicate products.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.1.0"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for",
    "from", "has", "have", "in", "into", "is", "it", "its",
    "of", "on", "or", "that", "the", "their", "this", "to",
    "with", "will", "new", "says", "said", "report", "reports",
    "amid", "year", "years", "2026",
}

TOPIC_TERMS = {
    "acquisition", "acquire", "merger", "supplier", "supply",
    "chain", "bottleneck", "capacity", "casting", "castings",
    "forging", "forge", "qualification", "quality",
    "manufacturing", "production", "factory", "plant",
    "facility", "expansion", "shortage", "shortages",
    "backlog", "downtime", "maintenance", "scrap", "rework",
    "grid", "energy", "utility", "infrastructure",
    "construction", "logistics", "warehouse", "robotics",
    "automation", "data", "center", "semiconductor",
    "aerospace", "aircraft", "engine", "engines", "space",
    "demand", "risk",
}

PROBLEM_PHRASES = [
    (
        {"casting", "bottleneck"},
        "Aerospace casting capacity bottlenecks",
    ),
    (
        {"forging", "bottleneck"},
        "Aerospace forging capacity bottlenecks",
    ),
    (
        {"supplier", "bottleneck"},
        "Supplier capacity and qualification bottlenecks",
    ),
    (
        {"supply", "chain"},
        "Supply-chain capacity and disruption risk",
    ),
    (
        {"factory", "production"},
        "Factory ramp and production-readiness constraints",
    ),
    (
        {"plant", "production"},
        "Plant ramp and production-readiness constraints",
    ),
    (
        {"grid", "planning"},
        "Grid planning and infrastructure constraints",
    ),
    (
        {"capacity", "manufacturing"},
        "Manufacturing capacity constraints",
    ),
]


def norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip().lower()


def tokens(text: str) -> set[str]:
    words = re.findall(
        r"[a-z0-9]+",
        norm(text),
    )

    return {
        word
        for word in words
        if len(word) >= 3
        and word not in STOPWORDS
    }


def signal_text(
    item: dict[str, Any],
) -> str:

    original = (
        item.get("original_signal")
        or {}
    )

    parts = [
        item.get("title"),
        item.get("industry"),
        original.get("title"),
        original.get("summary"),
        original.get("industry"),
    ]

    evidence = (
        item.get("evidence")
        or {}
    )

    for key in (
        "operational_signals",
        "value_signals",
        "ai_executable_signals",
        "business_change_signals",
        "high_impact_signals",
    ):
        values = evidence.get(key) or []

        if isinstance(values, list):
            parts.extend(values)

    return " ".join(
        str(value or "")
        for value in parts
    )


def topic_signature(
    item: dict[str, Any],
) -> set[str]:

    return {
        token
        for token in tokens(
            signal_text(item)
        )
        if token in TOPIC_TERMS
    }


def jaccard(
    a: set[str],
    b: set[str],
) -> float:

    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def industry(
    item: dict[str, Any],
) -> str:

    original = (
        item.get("original_signal")
        or {}
    )

    return norm(
        item.get("industry")
        or original.get("industry")
    )


def related(
    a: dict[str, Any],
    b: dict[str, Any],
) -> bool:

    sa = topic_signature(a)
    sb = topic_signature(b)

    overlap = sa & sb

    ia = industry(a)
    ib = industry(b)

    if (
        len(overlap) >= 3
        and jaccard(sa, sb) >= 0.24
    ):
        return True

    if (
        ia
        and ib
        and ia == ib
        and len(overlap) >= 2
    ):
        return True

    specific = {
        "bottleneck",
        "capacity",
        "casting",
        "forging",
        "supplier",
        "qualification",
    }

    if len(
        overlap & specific
    ) >= 2:
        return True

    return False


def connected_components(
    items: list[dict[str, Any]],
) -> list[list[int]]:

    count = len(items)

    adjacency = [
        []
        for _ in range(count)
    ]

    for i in range(count):
        for j in range(
            i + 1,
            count,
        ):
            if related(
                items[i],
                items[j],
            ):
                adjacency[i].append(j)
                adjacency[j].append(i)

    seen = set()
    components = []

    for i in range(count):

        if i in seen:
            continue

        stack = [i]
        seen.add(i)
        component = []

        while stack:
            current = stack.pop()
            component.append(current)

            for nxt in adjacency[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)

        components.append(component)

    return components


def infer_problem(
    cluster: list[dict[str, Any]],
) -> str:

    signature = set()

    for item in cluster:
        signature |= topic_signature(
            item
        )

    for required, label in PROBLEM_PHRASES:
        if required <= signature:
            return label

    common = Counter()

    for item in cluster:
        common.update(
            topic_signature(item)
        )

    terms = [
        key
        for key, _ in common.most_common(5)
    ]

    if terms:
        return (
            "Operational opportunity around "
            + ", ".join(terms)
        )

    return (
        "Operational opportunity "
        "requiring product discovery"
    )


def unique_sources(
    cluster: list[dict[str, Any]],
) -> list[str]:

    sources = []

    for item in cluster:

        original = (
            item.get("original_signal")
            or {}
        )

        source = (
            item.get("source")
            or original.get("source")
        )

        if (
            source
            and source not in sources
        ):
            sources.append(source)

        enrichment = (
            original.get(
                "evidence_enrichment"
            )
            or {}
        )

        for evidence in (
            enrichment.get("sources")
            or []
        ):
            source = evidence.get(
                "source"
            )

            if (
                source
                and source not in sources
            ):
                sources.append(source)

    return sources


def synthesize(
    cluster: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:

    scores = [
        int(
            item.get(
                "radar_score",
                0,
            )
            or 0
        )
        for item in cluster
    ]

    titles = [
        item.get("title")
        or (
            item.get("original_signal")
            or {}
        ).get("title")
        or "Untitled"
        for item in cluster
    ]

    industries = [
        industry(item)
        for item in cluster
        if industry(item)
    ]

    if industries:
        industry_name = (
            Counter(industries)
            .most_common(1)[0][0]
            .title()
        )
    else:
        industry_name = "Unknown"

    sources = unique_sources(
        cluster
    )

    problem = infer_problem(
        cluster
    )

    signatures = sorted(
        set().union(
            *(
                topic_signature(item)
                for item in cluster
            )
        )
    )

    confidence = min(
        100,
        round(
            (
                max(scores)
                if scores
                else 0
            ) * 0.65
            + min(
                20,
                max(
                    0,
                    len(cluster) - 1,
                ) * 4,
            )
            + min(
                15,
                len(sources) * 2,
            )
        ),
    )

    return {
        "cluster_id":
            f"cluster-{index:03d}",

        "cluster_version":
            VERSION,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "industry":
            industry_name,

        "problem_statement":
            problem,

        "cluster_score":
            confidence,

        "signal_count":
            len(cluster),

        "independent_source_count":
            len(sources),

        "independent_sources":
            sources,

        "topic_signature":
            signatures,

        "member_titles":
            titles,

        "member_signal_ids": [
            item.get("signal_id")
            or (
                item.get(
                    "original_signal"
                )
                or {}
            ).get("signal_id")
            for item in cluster
        ],

        "member_scores":
            scores,

        "recommended_next_action": (
            "SEND_CLUSTER_TO_PRODUCT_DISCOVERY"
            if confidence >= 70
            else
            "HOLD_FOR_MORE_EVIDENCE"
        ),
    }


def main() -> int:

    input_dir = Path(
        "product-discovery/radar-output"
    )

    output_dir = Path(
        "product-discovery/opportunity-clusters"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old in output_dir.glob(
        "*.json"
    ):
        old.unlink()

    promoted = []

    for path in input_dir.glob(
        "*-radar.json"
    ):

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if (
            data.get("disposition")
            == "PROMOTE_TO_DISCOVERY"
        ):
            promoted.append(data)

    if not promoted:
        print(
            "No promoted Radar results "
            "available to cluster."
        )
        return 0

    components = connected_components(
        promoted
    )

    clusters = []

    for index, component in enumerate(
        components,
        start=1,
    ):

        members = [
            promoted[i]
            for i in component
        ]

        cluster = synthesize(
            members,
            index,
        )

        clusters.append(
            cluster
        )

        output_path = (
            output_dir
            / f"{cluster['cluster_id']}.json"
        )

        output_path.write_text(
            json.dumps(
                cluster,
                indent=2,
            ),
            encoding="utf-8",
        )

    index_data = {
        "clusterer_version":
            VERSION,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "promoted_signal_count":
            len(promoted),

        "cluster_count":
            len(clusters),

        "clusters":
            clusters,
    }

    (
        output_dir
        / "index.json"
    ).write_text(
        json.dumps(
            index_data,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print(
        "JAKEAI OPPORTUNITY CLUSTERER — STAGE 0C"
    )
    print("=" * 70)

    print(
        f"Promoted signals: "
        f"{len(promoted)}"
    )

    print(
        f"Opportunity clusters: "
        f"{len(clusters)}"
    )

    print()

    for cluster in sorted(
        clusters,
        key=lambda item:
            item["cluster_score"],
        reverse=True,
    ):

        print(
            f"{cluster['cluster_score']}/100 | "
            f"{cluster['industry']} | "
            f"{cluster['signal_count']} signals | "
            f"{cluster['problem_statement']}"
        )

        print(
            f"  Next: "
            f"{cluster['recommended_next_action']}"
        )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
