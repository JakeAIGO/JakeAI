"""
JakeAI News / Opportunity Signal Ingestor
Stage 0A

Scans public news feeds for operational and commercial signals
that may reveal valuable Autonomous Workflow Skill opportunities.

No API keys required.
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


VERSION = "0.1.0"

SEARCH_QUERIES = [
    '"factory opening" manufacturing',
    '"new plant" manufacturing',
    '"supplier acquisition" manufacturing',
    'aerospace supplier capacity bottleneck',
    'manufacturing shortage bottleneck automation',
    'factory expansion production capacity',
    'supply chain acquisition integration',
    'robotics factory deployment',
    'construction labor shortage technology',
    'warehouse automation expansion',
    'energy infrastructure planning',
    'grid infrastructure optimization',
    'data center power capacity',
    'manufacturing quality scrap rework',
    'industrial maintenance downtime',
]


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def google_news_rss_url(query: str) -> str:
    encoded = urllib.parse.quote(query)
    return (
        f"https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )


def fetch_feed(query: str) -> list[dict]:
    url = google_news_rss_url(query)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 JakeAI Opportunity Radar/0.1"
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read()

    root = ET.fromstring(data)

    results = []

    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        published = item.findtext("pubDate") or ""

        source_element = item.find("source")
        source_name = (
            source_element.text.strip()
            if source_element is not None
            and source_element.text
            else "Google News"
        )

        results.append(
            {
                "title": clean_html(title),
                "url": link,
                "summary": clean_html(description),
                "published_at": published,
                "source": source_name,
                "search_query": query,
            }
        )

    return results


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:70]


def classify_industry(text: str) -> str:
    text = text.lower()

    categories = {
        "Aerospace": [
            "aerospace",
            "aircraft",
            "aviation",
            "engine",
            "jet",
        ],
        "Manufacturing": [
            "factory",
            "manufacturing",
            "production",
            "plant",
            "supplier",
        ],
        "Energy and Utilities": [
            "energy",
            "grid",
            "utility",
            "power",
            "electricity",
        ],
        "Construction": [
            "construction",
            "contractor",
            "building",
            "jobsite",
        ],
        "Logistics and Warehousing": [
            "warehouse",
            "logistics",
            "distribution",
            "freight",
        ],
        "Robotics": [
            "robot",
            "robotics",
            "autonomous",
        ],
        "Data Centers": [
            "data center",
            "datacenter",
            "compute",
        ],
    }

    scores = {}

    for industry, terms in categories.items():
        scores[industry] = sum(
            1 for term in terms if term in text
        )

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "General Industry"

    return best


def deduplicate(items: list[dict]) -> list[dict]:
    seen = set()
    output = []

    for item in items:
        key = re.sub(
            r"[^a-z0-9]",
            "",
            item["title"].lower()
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def convert_to_signal(
    article: dict,
    index: int,
) -> dict:

    combined = article["title"] + " " + article["summary"]

    industry = classify_industry(combined)

    return {
        "signal_id": (
            f"news-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            f"-{index:04d}"
        ),
        "signal_type": "PUBLIC_NEWS",
        "title": article["title"],
        "summary": article["summary"],
        "industry": industry,
        "source": article["source"],
        "source_url": article["url"],
        "published_at": article["published_at"],
        "discovery_query": article["search_query"],
        "buyer": "UNRESOLVED",
        "work_created": "UNRESOLVED",
        "economic_value": "UNRESOLVED",
        "repeatable": "UNRESOLVED",
        "independent_sources": 1,
        "ingestion": {
            "engine": "JakeAI News Signal Ingestor",
            "version": VERSION,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def save_signals(signals: list[dict]) -> None:

    output_dir = Path(
        "product-discovery/live-signals"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old_file in output_dir.glob("*.json"):
        old_file.unlink()

    for signal in signals:

        filename = (
            f"{signal['signal_id']}-"
            f"{slug(signal['title'])}.json"
        )

        path = output_dir / filename

        with path.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                signal,
                f,
                indent=2,
                ensure_ascii=False,
            )


def main() -> int:

    max_articles = 40

    if len(sys.argv) > 1:
        try:
            max_articles = int(sys.argv[1])
        except ValueError:
            print("Article count must be an integer.")
            return 2

    collected = []

    print("=" * 70)
    print("JAKEAI NEWS / OPPORTUNITY SIGNAL INGESTOR")
    print("=" * 70)

    for query in SEARCH_QUERIES:

        print(f"Scanning: {query}")

        try:
            articles = fetch_feed(query)
            collected.extend(articles[:10])

        except Exception as exc:
            print(
                f"WARNING: feed failed: "
                f"{query}: {exc}"
            )

    collected = deduplicate(collected)
    collected = collected[:max_articles]

    signals = [
        convert_to_signal(article, index + 1)
        for index, article
        in enumerate(collected)
    ]

    save_signals(signals)

    print()
    print(
        f"Unique live signals captured: "
        f"{len(signals)}"
    )

    industries = {}

    for signal in signals:
        industry = signal["industry"]
        industries[industry] = (
            industries.get(industry, 0) + 1
        )

    print()
    print("Industry distribution:")

    for industry, count in sorted(
        industries.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {industry}: {count}")

    print()
    print(
        "Output directory: "
        "product-discovery/live-signals/"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
