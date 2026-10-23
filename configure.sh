#!/usr/bin/env bash
# Write .firebaserc, app/Config/Secrets.xcconfig, and functions/.env from capy.env.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$ROOT/scripts/configure.py" "$@"
