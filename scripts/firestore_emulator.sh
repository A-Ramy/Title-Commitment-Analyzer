#!/usr/bin/env bash
# Starts the local Firestore emulator for the tests (needs Java 11+ and Node):
#   scripts/firestore_emulator.sh &   then   FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 uv run pytest
set -euo pipefail
JAR=$(ls ~/.cache/firebase/emulators/cloud-firestore-emulator-*.jar 2>/dev/null | tail -1 || true)
if [ -z "$JAR" ]; then
  npx --yes firebase-tools@13.29.1 setup:emulators:firestore
  JAR=$(ls ~/.cache/firebase/emulators/cloud-firestore-emulator-*.jar | tail -1)
fi
exec java -jar "$JAR" --host=127.0.0.1 --port=8085
