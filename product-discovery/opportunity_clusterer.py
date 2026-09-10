"""
JakeAI Opportunity Clusterer Regression Test

Confirms that:
1. Closely related signals cluster together.
2. Unrelated promoted opportunities remain separate.
3. Broad terms such as capacity, automation, or infrastructure
   do not collapse unrelated industries into one opportunity.
"""

from opportunity_clusterer import (
    connected_components,
    related,
    synthesize,
)


def signal(signal_id, title, industry, terms, score=80):
    return {
        "signal_id": signal_id,
        "title": title,
        "industry": industry,
        "radar_score": score,
        "disposition": "PROMOTE_TO_DISCOVERY",
        "source": f"Source {signal_id}",
        "original_signal": {
            "signal_id": signal_id,
            "title": title,
            "industry": industry,
            "summary": title,
            "source": f"Source {signal_id}",
        },
        "evidence": {
            "operational_signals": terms,
            "value_signals": [],
            "ai_executable_signals": [],
            "business_change_signals": [],
            "high_impact_signals": [],
        },
    }


signals = [
    signal(
        "aero-1",
        "Aerospace engine casting supplier bottleneck limits capacity",
        "Aerospace",
        ["bottleneck", "capacity", "supplier", "production"],
        92,
    ),
    signal(
        "aero-2",
        "Aircraft engine supplier capacity bottleneck affects castings",
        "Aerospace",
        ["bottleneck", "capacity", "supplier", "shortage"],
        88,
    ),
    signal(
        "mfg-1",
        "Semiconductor factory automation improves inspection throughput",
        "Manufacturing",
        ["automation", "quality"],
        78,
    ),
    signal(
        "energy-1",
        "Utility grid infrastructure planning addresses reliability",
        "Energy and Utilities",
        ["grid", "infrastructure"],
        76,
    ),
    signal(
        "logistics-1",
        "Warehouse robotics deployment changes logistics operations",
        "Logistics and Warehousing",
        ["warehouse", "robotics", "logistics"],
        74,
    ),
]


assert related(signals[0], signals[1]), (
    "FAIL: Related aerospace bottleneck signals were not matched."
)

for unrelated_index in (2, 3, 4):
    assert not related(signals[0], signals[unrelated_index]), (
        "FAIL: Aerospace signal incorrectly matched an unrelated opportunity."
    )
    assert not related(signals[1], signals[unrelated_index]), (
        "FAIL: Aerospace signal incorrectly matched an unrelated opportunity."
    )


components = connected_components(signals)

assert len(components) == 4, (
    f"FAIL: Expected 4 opportunity clusters, got {len(components)}."
)

sizes = sorted(
    (len(component) for component in components),
    reverse=True,
)

assert sizes == [2, 1, 1, 1], (
    f"FAIL: Expected cluster sizes [2, 1, 1, 1], got {sizes}."
)


clusters = []

for index, component in enumerate(components, start=1):
    members = [signals[i] for i in component]
    clusters.append(synthesize(members, index))


aerospace_clusters = [
    cluster
    for cluster in clusters
    if cluster["signal_count"] == 2
]

assert len(aerospace_clusters) == 1, (
    "FAIL: Expected exactly one two-signal aerospace cluster."
)

assert aerospace_clusters[0]["industry"] == "Aerospace", (
    "FAIL: Related aerospace cluster received the wrong industry."
)


print("=" * 70)
print("JAKEAI OPPORTUNITY CLUSTERER REGRESSION TEST")
print("=" * 70)
print("PASS")
print()
print("Input promoted signals: 5")
print("Expected clusters: 4")
print(f"Actual clusters: {len(clusters)}")
print("Cluster sizes:", sizes)
print()
print("Related aerospace signals: KEPT TOGETHER")
print("Manufacturing opportunity: KEPT SEPARATE")
print("Energy opportunity: KEPT SEPARATE")
print("Logistics opportunity: KEPT SEPARATE")
print("=" * 70)
