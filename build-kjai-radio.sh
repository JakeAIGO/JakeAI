#!/usr/bin/env bash
set -euo pipefail
mkdir -p radio
AUDIO_URL='https://sdmntprcentralus.oaiusercontent.com/files/00000000-2a1c-81f5-9af0-747b58a06114/raw?se=2026-09-25T16%3A54%3A48Z&sp=r&sv=2026-02-06&sr=b&scid=3bf8574d-eafe-5f37-84ac-dcebd91fb8a6&skoid=de71a0d5-fb02-4fce-be69-9296aced242b&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-09-25T15%3A28%3A29Z&ske=2026-09-26T15%3A28%3A29Z&sks=b&skv=2026-02-06&sig=bR8m5AFLk7tCrYvIOu5pQjk2WPSPYUJc4nL%2BPCrz/5U%3D'
echo "Fetching approved KJAI Broadcast 002 audio for this production build..."
curl --retry 3 --retry-delay 2 -fsSL "$AUDIO_URL" -o /tmp/kjai-public.b64
base64 -d /tmp/kjai-public.b64 > radio/KJAI_Broadcast_002_QA.mp3
echo "f2daa29c9abcf1ab02d2bdd836e9a84c217ad59d8511ea2abedc9f1a097fad43  radio/KJAI_Broadcast_002_QA.mp3" | sha256sum -c -
rm -f /tmp/kjai-public.b64
echo "KJAI Broadcast 002 public audio staged."
