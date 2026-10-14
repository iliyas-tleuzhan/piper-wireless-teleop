#!/usr/bin/env bash
# Install only this bundle's role dependencies into a private virtual environment.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ROLE="${1:-}"
case "$ROLE" in master|slave) ;; *) echo "Usage: bash scripts/install_runtime.sh master|slave" >&2; exit 2 ;; esac
if [[ ! -f "$ROOT/requirements-$ROLE.txt" ]]; then
  echo "This bundle does not contain the requested role." >&2; exit 2
fi
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements-$ROLE.txt"
echo "Installed $ROLE runtime. Run from $ROOT with .venv/bin/python -m piper_wireless_teleop.dual_arm $ROLE ..."
