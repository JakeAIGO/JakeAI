name: JakeAI Opportunity Radar Test

on:
  workflow_dispatch:

jobs:
  run-radar:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set Up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Scan Live Public News
        run: |
          python product-discovery/news_ingestor.py 40

      - name: Run Opportunity Radar Across Live Signals
        shell: bash
        run: |
          count=0

          for signal in product-discovery/live-signals/*.json; do
            if [ -f "$signal" ]; then
              echo ""
              echo "======================================================================"
              echo "EVALUATING: $signal"
              echo "======================================================================"

              python product-discovery/opportunity_radar.py "$signal"
              count=$((count + 1))
            fi
          done

          echo ""
          echo "Signals evaluated: $count"

          if [ "$count" -eq 0 ]; then
            echo "ERROR: No live signals were captured."
            exit 1
          fi

      - name: Enrich Signals Needing More Evidence
        run: |
          python product-discovery/evidence_enricher.py

      - name: Preserve First-Pass Radar Results
        shell: bash
        run: |
          mkdir -p product-discovery/radar-first-pass

          cp product-discovery/radar-output/*.json \
             product-discovery/radar-first-pass/ 2>/dev/null || true

      - name: Re-score Enriched Signals
        shell: bash
        run: |
          count=0

          for signal in product-discovery/enriched-signals/*.json; do
            if [ -f "$signal" ]; then
              echo ""
              echo "======================================================================"
              echo "RE-SCORING ENRICHED SIGNAL: $signal"
              echo "======================================================================"

              python product-discovery/opportunity_radar.py "$signal"
              count=$((count + 1))
            fi
          done

          echo ""
          echo "Enriched signals re-scored: $count"

      - name: Cluster Promoted Opportunities
        run: |
          python product-discovery/opportunity_clusterer.py

      - name: Convert Qualified Clusters To Product Discovery Inputs
        run: |
          python product-discovery/cluster_to_discovery.py

      - name: Run Product Discovery On Qualified Clusters
        shell: bash
        run: |
          mkdir -p product-discovery/candidates
          count=0

          for candidate in product-discovery/discovery-inputs/*.json; do
            if [ -f "$candidate" ]; then
              echo ""
              echo "======================================================================"
              echo "PRODUCT DISCOVERY: $candidate"
              echo "======================================================================"

              python product-discovery/discovery_engine.py "$candidate"
              count=$((count + 1))
            fi
          done

          echo ""
          echo "Product Discovery inputs evaluated: $count"

      - name: Summarize Test 8 Results
        run: |
          python - <<'PY'
          import json
          from pathlib import Path

          print("=" * 70)
          print("JAKEAI OPPORTUNITY RADAR — TEST #8")
          print("=" * 70)

          cluster_index = Path(
              "product-discovery/opportunity-clusters/index.json"
          )

          if cluster_index.exists():
              data = json.loads(
                  cluster_index.read_text(encoding="utf-8")
              )

              print(
                  "Promoted signals:",
                  data.get("promoted_signal_count", 0),
              )

              print(
                  "Opportunity clusters:",
                  data.get("cluster_count", 0),
              )

          discovery_inputs = list(
              Path(
                  "product-discovery/discovery-inputs"
              ).glob("*.json")
          )

          blocked = list(
              Path(
                  "product-discovery/discovery-blocked"
              ).glob("*.json")
          )

          candidates = []

          for path in Path(
              "product-discovery/candidates"
          ).glob("*.json"):
              try:
                  candidates.append(
                      json.loads(
                          path.read_text(
                              encoding="utf-8"
                          )
                      )
                  )
              except Exception:
                  pass

          print(
              "Discovery inputs created:",
              len(discovery_inputs),
          )

          print(
              "Blocked transfers:",
              len(blocked),
          )

          print(
              "Discovery candidates evaluated:",
              len(candidates),
          )

          for item in sorted(
              candidates,
              key=lambda x:
