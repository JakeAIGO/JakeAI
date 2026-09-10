"""
JakeAI News / Opportunity Signal Ingestor
Stage 0A

Version 0.2.0

Purpose:
Capture live public operational and commercial signals that may reveal
valuable Autonomous Workflow Skill opportunities.

Reliability design:
- Google News RSS
- Bing News RSS
- Parallel fetching
- Short network timeouts
- Cross-source deduplication
- No fabricated fallback evidence
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path


VERSION = "0.2.0"
FETCH_TIMEOUT = 8
MAX_WORKERS = 8

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
    text = re.sub(
        r"<[^>]+>",
        " ",
        text or "",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def google_news_rss_url(query: str) -> str:
    encoded = urllib.parse.quote(query)

    return (
        "https://news.google.com/rss/search?"
        f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )


def bing_news_rss_url(query: str) -> str:
    encoded = urllib.parse.quote(query)

    return (
        "https://www.bing.com/news/search?"
        f"q={encoded}&format=rss"
    )


def request_xml(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "JakeAI Opportunity Radar/0.2",
            "Accept":
                "application/rss+xml,"
                "application/xml,text/xml,*/*",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=FETCH_TIMEOUT,
    ) as response:
        return response.read()


def parse_rss(
    data: bytes,
    query: str,
    provider: str,
) -> list[dict]:

    root = ET.fromstring(data)

    results = []

    for item in root.findall(".//item"):
        title = clean_html(
            item.findtext("title") or ""
        )

        link = (
            item.findtext("link")
            or ""
        ).strip()

        description = clean_html(
            item.findtext("description")
            or ""
        )

        published = (
            item.findtext("pubDate")
            or ""
        ).strip()

        source_name = ""

        source_element = item.find(
            "source"
        )

        if (
            source_element is not None
            and source_element.text
        ):
            source_name = (
                source_element.text.strip()
            )

        if not source_name:
            source_name = provider

        if not title or not link:
            continue

        results.append(
            {
                "title": title,
                "url": link,
                "summary": description,
                "published_at": published,
                "source": source_name,
                "feed_provider": provider,
                "search_query": query,
            }
        )

    return results


def fetch_provider(
    provider: str,
    query: str,
) -> list[dict]:

    if provider == "Google News":
        url = google_news_rss_url(
            query
        )

    elif provider == "Bing News":
        url = bing_news_rss_url(
            query
        )

    else:
        raise ValueError(
            f"Unknown provider: {provider}"
        )

    data = request_xml(url)

    return parse_rss(
        data,
        query,
        provider,
    )


def fetch_task(
    provider: str,
    query: str,
) -> dict:

    try:
        articles = fetch_provider(
            provider,
            query,
        )

        return {
            "provider": provider,
            "query": query,
            "articles": articles,
            "error": None,
        }

    except Exception as exc:
        return {
            "provider": provider,
            "query": query,
            "articles": [],
            "error": str(exc),
        }


def slug(text: str) -> str:
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    )

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

    for industry, terms in (
        categories.items()
    ):
        scores[industry] = sum(
            1
            for term in terms
            if term in text
        )

    best = max(
        scores,
        key=scores.get,
    )

    if scores[best] == 0:
        return "General Industry"

    return best


def title_key(title: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        title.lower(),
    )


def deduplicate(
    items: list[dict],
) -> list[dict]:

    records = {}

    for item in items:
        key = title_key(
            item["title"]
        )

        if not key:
            continue

        if key not in records:
            item["independent_sources"] = 1
            item["feed_providers"] = [
                item.get(
                    "feed_provider",
                    "Unknown",
                )
            ]

            records[key] = item
            continue

        existing = records[key]

        providers = set(
            existing.get(
                "feed_providers",
                [],
            )
        )

        provider = item.get(
            "feed_provider"
        )

        if (
            provider
            and provider not in providers
        ):
            providers.add(provider)

            existing[
                "independent_sources"
            ] = max(
                2,
                existing.get(
                    "independent_sources",
                    1,
                ),
            )

        existing[
            "feed_providers"
        ] = sorted(providers)

        if (
            len(item.get("summary", ""))
            >
            len(
                existing.get(
                    "summary",
                    "",
                )
            )
        ):
            existing["summary"] = (
                item["summary"]
            )

    return list(
        records.values()
    )


def convert_to_signal(
    article: dict,
    index: int,
) -> dict:

    combined = (
        article["title"]
        + " "
        + article.get(
            "summary",
            "",
        )
    )

    industry = classify_industry(
        combined
    )

    date_code = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d")

    return {
        "signal_id":
            f"news-{date_code}-{index:04d}",

        "signal_type":
            "PUBLIC_NEWS",

        "title":
            article["title"],

        "summary":
            article.get(
                "summary",
                "",
            ),

        "industry":
            industry,

        "source":
            article.get(
                "source",
                "Unknown",
            ),

        "source_url":
            article["url"],

        "published_at":
            article.get(
                "published_at",
                "",
            ),

        "discovery_query":
            article.get(
                "search_query",
                "",
            ),

        "feed_providers":
            article.get(
                "feed_providers",
                [
                    article.get(
                        "feed_provider",
                        "Unknown",
                    )
                ],
            ),

        "buyer":
            "UNRESOLVED",

        "work_created":
            "UNRESOLVED",

        "economic_value":
            "UNRESOLVED",

        "repeatable":
            "UNRESOLVED",

        "independent_sources":
            article.get(
                "independent_sources",
                1,
            ),

        "ingestion": {
            "engine":
                "JakeAI News Signal Ingestor",

            "version":
                VERSION,

            "ingested_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        },
    }


def save_signals(
    signals: list[dict],
) -> None:

    output_dir = Path(
        "product-discovery/live-signals"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old_file in output_dir.glob(
        "*.json"
    ):
        old_file.unlink()

    for signal in signals:
        filename = (
            f"{signal['signal_id']}-"
            f"{slug(signal['title'])}.json"
        )

        path = (
            output_dir
            / filename
        )

        path.write_text(
            json.dumps(
                signal,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def main() -> int:
    max_articles = 40

    if len(sys.argv) > 1:
        try:
            max_articles = int(
                sys.argv[1]
            )

        except ValueError:
            print(
                "Article count must "
                "be an integer."
            )

            return 2

    print("=" * 70)
    print(
        "JAKEAI NEWS / "
        "OPPORTUNITY SIGNAL INGESTOR v0.2"
    )
    print("=" * 70)

    tasks = []

    for query in SEARCH_QUERIES:
        for provider in (
            "Google News",
            "Bing News",
        ):
            tasks.append(
                (
                    provider,
                    query,
                )
            )

    collected = []

    provider_successes = {
        "Google News": 0,
        "Bing News": 0,
    }

    provider_failures = {
        "Google News": 0,
        "Bing News": 0,
    }

    print(
        "Scanning Google News "
        "and Bing News in parallel..."
    )
    print()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                fetch_task,
                provider,
                query,
            )
            for provider, query
            in tasks
        ]

        for future in (
            concurrent.futures.as_completed(
                futures
            )
        ):
            result = future.result()

            provider = result[
                "provider"
            ]

            query = result[
                "query"
            ]

            articles = result[
                "articles"
            ]

            error = result[
                "error"
            ]

            if error:
                provider_failures[
                    provider
                ] += 1

                print(
                    f"WARNING: "
                    f"{provider} failed | "
                    f"{query} | "
                    f"{error}"
                )

                continue

            provider_successes[
                provider
            ] += 1

            print(
                f"{provider}: "
                f"{len(articles)} results | "
                f"{query}"
            )

            collected.extend(
                articles[:10]
            )

    collected = deduplicate(
        collected
    )

    collected = collected[
        :max_articles
    ]

    signals = [
        convert_to_signal(
            article,
            index + 1,
        )
        for index, article
        in enumerate(collected)
    ]

    save_signals(signals)

    print()
    print("PROVIDER HEALTH")

    for provider in (
        "Google News",
        "Bing News",
    ):
        print(
            f"{provider}: "
            f"{provider_successes[provider]} "
            f"successful queries, "
            f"{provider_failures[provider]} "
            f"failed queries"
        )

    print()
    print(
        "Unique live signals captured: "
        f"{len(signals)}"
    )

    industries = {}

    for signal in signals:
        industry = signal[
            "industry"
        ]

        industries[industry] = (
            industries.get(
                industry,
                0,
            )
            + 1
        )

    print()
    print("Industry distribution:")

    for industry, count in sorted(
        industries.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(
            f"  {industry}: {count}"
        )

    print()
    print(
        "Output directory: "
        "product-discovery/live-signals/"
    )

    if not signals:
        print()
        print(
            "ERROR: No live signals "
            "were returned by either "
            "public news provider."
        )

        print(
            "No synthetic evidence "
            "was generated."
        )

        print("=" * 70)

        return 1

    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
