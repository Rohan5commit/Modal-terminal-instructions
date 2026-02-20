#!/bin/bash
set -euo pipefail

usage() {
  /bin/cat <<'EOF'
Usage:
  modal-agent-runner -- <command> [args...]
  modal-agent-runner -c "<shell command>"
  modal-agent-runner "<shell command>"

Routes agent terminal commands to Modal via scripts/modal_exec.sh.
EOF
}

SCRIPT_PATH="${BASH_SOURCE[0]}"
while [[ -L "$SCRIPT_PATH" ]]; do
  LINK_TARGET="$(/usr/bin/readlink "$SCRIPT_PATH")"
  if [[ "$LINK_TARGET" == /* ]]; then
    SCRIPT_PATH="$LINK_TARGET"
  else
    SCRIPT_PATH="$(cd "${SCRIPT_PATH%/*}" && /bin/pwd)/$LINK_TARGET"
  fi
done
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"
MODAL_EXEC="${ROOT_DIR}/scripts/modal_exec.sh"

if [[ ! -x "$MODAL_EXEC" ]]; then
  echo "Error: missing executable ${MODAL_EXEC}" >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

cd "$ROOT_DIR"

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  -c|--cmd)
    shift
    if [[ $# -eq 0 ]]; then
      echo "Error: missing command after -c/--cmd" >&2
      exit 2
    fi
    exec "$MODAL_EXEC" -c "$1"
    ;;
  --)
    shift
    if [[ $# -eq 0 ]]; then
      echo "Error: missing command after --" >&2
      exit 2
    fi
    exec "$MODAL_EXEC" -- "$@"
    ;;
  *)
    if [[ $# -eq 1 ]]; then
      exec "$MODAL_EXEC" -c "$1"
    fi
    exec "$MODAL_EXEC" -- "$@"
    ;;
esac
