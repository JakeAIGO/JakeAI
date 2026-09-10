"""
JakeAI Evidence Enricher
Stage 0B of the Autonomous Product Discovery Pipeline

Purpose:
Take Opportunity Radar signals marked NEEDS_MORE_EVIDENCE
and automatically gather corroborating public evidence.

Pipeline:
Live News Ingestor
-> Opportunity Radar
-> Evidence Enricher
-> Radar Re-score
-> Product Discovery
-> Validation
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "0.1.0"


BUYER_HINTS = {
    "manufacturing": [
        "plant manager",
        "operations manager",
        "manufacturing engineer",
        "supply chain leader",
    ],
    "aerospace": [
        "aerospace operations leader",
        "supplier quality manager",
        "production planning leader",
    ],
    "energy": [
        "utility operations leader",
        "grid planning team",
        "energy infrastructure planner",
    ],
    "construction": [
        "construction operations leader",
        "project manager",
        "general contractor",
    ],
    "logistics": [
        "logistics operations leader",
        "warehouse manager",
        "supply chain manager",
    ],
    "robotics": [
        "robotics operations leader",
        "automation engineer",
        "facility operations manager",
    ],
    "data center": [
        "data center operations leader",
        "capacity planning team",
        "infrastructure manager",
    ],
}


WORK_PATTERNS = {
    "bottleneck": "Detect, rank, and monitor production bottlenecks",
    "shortage": "Monitor shortages and prioritize mitigation actions",
    "capacity": "Analyze capacity constraints and planning options",
    "supplier": "Monitor supplier risk, performance, and integration issues",
    "acquisition": "Coordinate acquisition integration workflows and operational risks",
    "merger": "Coordinate merger integration workflows and operational risks",
    "factory": "Track factory ramp-up, production readiness, and operating constraints",
    "plant": "Track plant ramp-up, production readiness, and operating constraints",
    "downtime": "Detect downtime patterns and prioritize corrective actions",
    "maintenance": "Prioritize maintenance risks and recommended interventions",
    "quality": "Monitor quality signals, defects, and corrective actions",
    "scrap": "Analyze scrap drivers and prioritize reduction opportunities",
    "rework": "Analyze rework drivers and corrective actions",
    "backlog": "Monitor backlog risk and prioritize recovery actions",
    "grid": "Analyze grid planning constraints and candidate infrastructure actions",
    "construction": "Coordinate construction risk, scheduling, and operational dependencies",
}


VALUE_PATTERNS = {
    "bottleneck": "Reduce delays, throughput loss, and constrained production capacity",
    "shortage": "Reduce disruption risk and time spent reacting to shortages",
    "capacity": "Improve capacity utilization and capital planning",
    "downtime": "Reduce downtime and associated production loss",
    "scrap": "Reduce material waste and production cost",
    "rework": "Reduce rework labor, delay, and quality cost",
    "supplier": "Reduce supplier disruption and integration risk",
    "quality": "Reduce defects, quality escapes, and corrective-action effort",
    "backlog": "Reduce backlog and improve delivery performance",
    "factory": "Improve production ramp speed and operational readiness",
    "plant": "Improve production ramp speed and operational readiness",
    "acquisition": "Reduce integration effort, duplication, and operational disruption",
    "merger": "Reduce integration effort, duplication, and operational disruption",
    "grid": "Reduce planning effort and improve infrastructure site decisions",
}


def normalize(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip().lower()


def clean_html(text: str) -> str:
    text = re.sub(
        r"<[^>]+>",
        " ",
        text or "",
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def google_news_url(query: str) -> str:
    encoded = urllib.parse.quote(query)

    return (
        "https://news.google.com/rss/search?"
        f"q={encoded}"
        "&hl=en-US&gl=US&ceid=US:en"
    )


def fetch_news(query: str) -> list[dict]:
    request = urllib.request.Request(
        google_news_url(query),
        headers={
            "User-Agent":
                "Mozilla/5.0 JakeAI Evidence Enricher/0.1"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:

        data = response.read()

    root = ET.fromstring(data)

    articles = []

    for item in root.findall(".//item"):
        source_element = item.find("source")

        source = (
            source_element.text.strip()
            if source_element is not None
            and source_element.text
            else "Unknown"
        )

        articles.append(
            {
                "title": clean_html(
                    item.findtext("title") or ""
                ),
                "url": item.findtext("link") or "",
                "summary": clean_html(
                    item.findtext("description") or ""
                ),
                "published_at":
                    item.findtext("pubDate") or "",
                "source": source,
            }
        )

    return articles


def build_research_query(
    signal: dict[str, Any],
) -> str:

    title = signal.get(
        "title",
        "",
    )

    title = re.sub(
        r"\s+-\s+[^-]+$",
        "",
        title,
    )

    words = re.findall(
        r"[A-Za-z0-9$£]+",
        title,
    )

    useful = [
        word
        for word in words
        if len(word) > 2
    ]

    return " ".join(
        useful[:12]
    )


def deduplicate_sources(
    articles: list[dict],
) -> list[dict]:

    seen_sources = set()
    unique = []

    for article in articles:
        source = normalize(
            article.get("source")
        )

        if not source:
            continue

        if source in seen_sources:
            continue

        seen_sources.add(source)
        unique.append(article)

    return unique


def infer_buyer(
    industry: str,
) -> str:

    industry_text = normalize(industry)

    for key, buyers in BUYER_HINTS.items():
        if key in industry_text:
            return "; ".join(buyers)

    return (
        "operations leader; "
        "process owner; "
        "business unit manager"
    )


def infer_work(
    text: str,
) -> str:

    for term, work in WORK_PATTERNS.items():
        if term in text:
            return work

    return (
        "Analyze the operational change, "
        "identify recurring work, "
        "and prioritize response actions"
    )


def infer_value(
    text: str,
) -> str:

    values = []

    for term, value in VALUE_PATTERNS.items():
        if term in text:
            values.append(value)

    if not values:
        return (
            "Potential reduction in manual analysis, "
            "delay, operational risk, or avoidable cost"
        )

    return "; ".join(
        dict.fromkeys(values)
    )


def infer_repeatability(
    evidence: list[dict],
    text: str,
) -> str:

    if len(evidence) >= 3:
        return (
            "LIKELY_REPEATABLE: multiple independent "
            "sources indicate a broader operational pattern"
        )

    repeatability_terms = [
        "industry",
        "companies",
        "manufacturers",
        "suppliers",
        "factories",
        "utilities",
        "operators",
    ]

    if any(
        term in text
        for term in repeatability_terms
    ):
        return (
            "POSSIBLY_REPEATABLE: signal appears broader "
            "than a single organization"
        )

    return "UNRESOLVED"


def enrich_signal(
    radar_result: dict[str, Any],
) -> dict[str, Any]:

    original = radar_result.get(
        "original_signal",
        {},
    )

    query = build_research_query(
        original
    )

    articles = fetch_news(query)

    independent = deduplicate_sources(
        articles
    )

    original_source = normalize(
        original.get("source")
    )

    corroborating = [
        article
        for article in independent
        if normalize(
            article.get("source")
        ) != original_source
    ]

    combined_text = normalize(
        " ".join(
            [
                original.get("title", ""),
                original.get("summary", ""),
            ]
            + [
                article.get("title", "")
                + " "
                + article.get("summary", "")
                for article in corroborating[:10]
            ]
        )
    )

    enriched = dict(original)

    enriched[
        "independent_sources"
    ] = max(
        1,
        len(corroborating) + 1,
    )

    enriched["buyer"] = infer_buyer(
        original.get(
            "industry",
            "",
        )
    )

    enriched["work_created"] = infer_work(
        combined_text
    )

    enriched["economic_value"] = infer_value(
        combined_text
    )

    enriched["repeatable"] = infer_repeatability(
        corroborating,
        combined_text,
    )

    enriched["why_it_matters"] = (
        enriched["economic_value"]
    )

    enriched["evidence_enrichment"] = {
        "version": VERSION,
        "researched_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "research_query": query,
        "independent_sources_found":
            len(corroborating),
        "sources": corroborating[:10],
    }

    return enriched


def process_directory(
    radar_dir: Path,
) -> tuple[int, int]:

    output_dir = Path(
        "product-discovery/enriched-signals"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old in output_dir.glob("*.json"):
        old.unlink()

    examined = 0
    enriched_count = 0

    for path in radar_dir.glob(
        "*-radar.json"
    ):

        examined += 1

        radar_result = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if radar_result.get(
            "disposition"
        ) != "NEEDS_MORE_EVIDENCE":

            continue

        try:
            enriched = enrich_signal(
                radar_result
            )

        except Exception as exc:
            print(
                f"WARNING: enrichment failed "
                f"for {path.name}: {exc}"
            )
            continue

        signal_id = (
            enriched.get("signal_id")
            or path.stem
        )

        safe_id = re.sub(
            r"[^A-Za-z0-9._-]",
            "-",
            str(signal_id),
        )

        output_path = (
            output_dir
            / f"{safe_id}-enriched.json"
        )

        output_path.write_text(
            json.dumps(
                enriched,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        enriched_count += 1

        print("=" * 70)
        print(
            f"ENRICHED: "
            f"{enriched.get('title')}"
        )
        print(
            f"Independent sources: "
            f"{enriched.get('independent_sources')}"
        )
        print(
            f"Buyer: "
            f"{enriched.get('buyer')}"
        )
        print(
            f"Work: "
            f"{enriched.get('work_created')}"
        )
        print(
            f"Value: "
            f"{enriched.get('economic_value')}"
        )
        print("=" * 70)

    return examined, enriched_count


def main() -> int:
    radar_dir = Path(
        "product-discovery/radar-output"
    )

    if not radar_dir.exists():
        print(
            "ERROR: radar-output directory "
            "does not exist."
        )
        return 2

    print("=" * 70)
    print(
        "JAKEAI EVIDENCE ENRICHER — STAGE 0B"
    )
    print("=" * 70)

    examined, enriched = process_directory(
        radar_dir
    )

    print()
    print(
        f"Radar results examined: {examined}"
    )
    print(
        f"Signals enriched: {enriched}"
    )
    print(
        "Output: "
        "product-discovery/enriched-signals/"
    )
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
