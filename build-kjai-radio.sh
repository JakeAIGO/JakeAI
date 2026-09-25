#!/usr/bin/env bash
set -euo pipefail
mkdir -p radio
if [ -z "${KJAI_PUBLIC_AUDIO_B64_URL:-}" ]; then
  echo "KJAI_PUBLIC_AUDIO_B64_URL is missing" >&2
  exit 1
fi
curl --retry 3 --retry-delay 2 -fsSL "${KJAI_PUBLIC_AUDIO_B64_URL}" -o /tmp/kjai-public.b64
base64 -d /tmp/kjai-public.b64 > radio/KJAI_Broadcast_002_QA.mp3
echo "f2daa29c9abcf1ab02d2bdd836e9a84c217ad59d8511ea2abedc9f1a097fad43  radio/KJAI_Broadcast_002_QA.mp3" | sha256sum -c -
rm -f /tmp/kjai-public.b64
echo "KJAI Broadcast 002 public audio staged."
