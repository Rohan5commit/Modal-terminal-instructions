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
SOURCE_PATH="${ROOT_DIR}/scripts/agent_terminal_runner.sh"

/bin/mkdir -p "$TARGET_DIR"
/bin/chmod +x "$SOURCE_PATH"
/bin/ln -sf "$SOURCE_PATH" "$TARGET_PATH"

/bin/cat <<EOF
Installed global agent terminal runner:
  ${TARGET_PATH} -> ${SOURCE_PATH}

Set this as your terminal command runner for each coding agent.
Examples:
  ${TARGET_PATH} -c "hostname"
  ${TARGET_PATH} -- ls -la
EOF
