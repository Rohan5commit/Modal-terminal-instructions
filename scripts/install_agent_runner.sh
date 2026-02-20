#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"

TARGET_DIR="${HOME}/.local/bin"
TARGET_PATH="${TARGET_DIR}/modal-agent-runner"

/bin/mkdir -p "$TARGET_DIR"
if [[ -e "$TARGET_PATH" || -L "$TARGET_PATH" ]]; then
  /bin/rm -f "$TARGET_PATH"
fi
/bin/cat > "$TARGET_PATH" <<'EOF'
#!/bin/bash
set -euo pipefail

usage() {
  /bin/cat <<'USAGE'
Usage:
  modal-agent-runner -- <command> [args...]
  modal-agent-runner -c "<shell command>"
  modal-agent-runner "<shell command>"

Routes agent terminal commands to Modal via scripts/modal_exec.sh in the current repo.
USAGE
}

find_repo_root() {
  if [[ -n "${MODAL_AGENT_REPO_ROOT:-}" ]]; then
    if [[ -x "${MODAL_AGENT_REPO_ROOT}/scripts/modal_exec.sh" ]] && [[ -f "${MODAL_AGENT_REPO_ROOT}/modal_tasks.py" ]]; then
      /bin/echo "${MODAL_AGENT_REPO_ROOT}"
      return 0
    fi
  fi

  local dir="$PWD"
  while true; do
    if [[ -x "${dir}/scripts/modal_exec.sh" ]] && [[ -f "${dir}/modal_tasks.py" ]]; then
      /bin/echo "${dir}"
      return 0
    fi
    if [[ "${dir}" == "/" ]]; then
      break
    fi
    dir="$(dirname "${dir}")"
  done

  return 1
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

ROOT_DIR="$(find_repo_root)" || {
  echo "Error: could not locate a Modal task-runner repo from \$PWD (${PWD})." >&2
  echo "Run from inside a clone containing scripts/modal_exec.sh and modal_tasks.py," >&2
  echo "or set MODAL_AGENT_REPO_ROOT to that clone path." >&2
  exit 2
}
MODAL_EXEC="${ROOT_DIR}/scripts/modal_exec.sh"

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
EOF
/bin/chmod +x "$TARGET_PATH"

/bin/cat <<EOF
Installed global agent terminal runner:
  ${TARGET_PATH}

Set this as your terminal command runner for each coding agent.
Examples:
  ${TARGET_PATH} -c "hostname"
  ${TARGET_PATH} -- ls -la
EOF
