#!/bin/bash
set -euo pipefail

usage() {
  /bin/cat <<'EOF'
Usage:
  ./scripts/modal_exec.sh [--sync-back|--no-sync-back] -- <command> [args...]
  ./scripts/modal_exec.sh [--sync-back|--no-sync-back] -c "<shell command>"

Runs commands in Modal via modal_tasks.py.
Default is --sync-back so file changes are written back locally.
EOF
}

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"
MODAL_PYTHON_BIN="${MODAL_PYTHON_BIN:-/usr/bin/python3}"
MODAL_RUN_FLAGS="${MODAL_RUN_FLAGS-}"
SYNC_BACK="${MODAL_SYNC_BACK:-1}"
MODAL_CPU="${MODAL_CPU:-6}"
MODAL_MEMORY_MB="${MODAL_MEMORY_MB:-14336}"

export MODAL_CPU
export MODAL_MEMORY_MB

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    -h|--help)
      usage
      exit 0
      ;;
    --sync-back)
      SYNC_BACK=1
      shift
      ;;
    --no-sync-back)
      SYNC_BACK=0
      shift
      ;;
    *)
      break
      ;;
  esac
done

if [[ "${1:-}" == "-c" || "${1:-}" == "--cmd" ]]; then
  shift
  if [[ $# -eq 0 ]]; then
    echo "Error: missing command after -c/--cmd" >&2
    exit 2
  fi
  cmd="$1"
  shift
  if [[ $# -gt 0 ]]; then
    echo "Error: extra arguments found after raw command string." >&2
    exit 2
  fi
else
  if [[ "${1:-}" == "--" ]]; then
    shift
  fi
  if [[ $# -eq 0 ]]; then
    echo "Error: missing command." >&2
    exit 2
  fi
  printf -v cmd '%q ' "$@"
  cmd="${cmd% }"
fi

workdir="$($MODAL_PYTHON_BIN - "$ROOT_DIR" "$PWD" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
cwd = Path(sys.argv[2]).resolve()

try:
    rel = cwd.relative_to(root)
except ValueError:
    raise SystemExit(2)

print("." if str(rel) == "" else rel.as_posix())
PY
)" || {
  echo "Error: run this command from inside the repository at $ROOT_DIR" >&2
  exit 2
}

cd "$ROOT_DIR"
sync_flag="--sync-back"
sync_back_norm="$(printf '%s' "$SYNC_BACK" | /usr/bin/tr '[:upper:]' '[:lower:]')"
if [[ "$sync_back_norm" == "0" || "$sync_back_norm" == "false" || "$sync_back_norm" == "no" ]]; then
  sync_flag="--no-sync-back"
fi

modal_cmd=("$MODAL_PYTHON_BIN" -m modal run)
if [[ -n "$MODAL_RUN_FLAGS" ]]; then
  read -r -a run_flag_parts <<< "$MODAL_RUN_FLAGS"
  modal_cmd+=("${run_flag_parts[@]}")
fi
modal_cmd+=(modal_tasks.py --cmd "$cmd" --workdir "$workdir" "$sync_flag")

exec "${modal_cmd[@]}"
