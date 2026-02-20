#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"

USER_DIR="${HOME}/Library/Application Support/Antigravity/User"
SETTINGS_PATH="${USER_DIR}/settings.json"
RUNNER="${HOME}/.local/bin/modal-agent-runner"
GEMINI_BASH="${ROOT_DIR}/.gemini/bin/bash"
GEMINI_ENV="${ROOT_DIR}/.gemini/.env"

echo "=== Workspace Policy Files ==="
/bin/ls -la \
  "${ROOT_DIR}/ANTIGRAVITY.md" \
  "${ROOT_DIR}/AGENTS.md" \
  "${ROOT_DIR}/.clinerules" \
  "${ROOT_DIR}/.rules/antigravity.rules" \
  "${ROOT_DIR}/.rules/codex.rules" \
  "${ROOT_DIR}/.vscode/settings.json"
echo

echo "=== Workspace Settings (Gemini + Modal env) ==="
python3 - "${ROOT_DIR}/.vscode/settings.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
settings = json.loads(path.read_text())

keys = [
    "geminicodeassist.rules",
    "geminicodeassist.agentYoloMode",
    "terminal.integrated.env.osx",
]
for k in keys:
    print(f"{k} = {settings.get(k)!r}")
PY
echo

if [[ "${IN_MODAL_TASK_RUNNER:-0}" == "1" ]]; then
  echo "=== Runtime Verification (running inside Modal) ==="
  hostname
  python3 - <<'PY'
import os
import platform
print(platform.system())
print(os.getenv("IN_MODAL_TASK_RUNNER"))
PY
  echo
  echo "User-level Antigravity checks skipped in Modal container."
  echo "Run ./scripts/check_antigravity_policy.sh locally to inspect macOS user settings."
  exit 0
fi

echo "=== Gemini Workspace Wrapper Files ==="
/bin/ls -la "${GEMINI_BASH}" "${GEMINI_ENV}" 2>/dev/null || true
echo
if [[ -f "${GEMINI_ENV}" ]]; then
  echo "--- ${GEMINI_ENV} ---"
  /bin/cat "${GEMINI_ENV}"
  echo
fi

echo "=== User Policy Files ==="
/bin/ls -la "${USER_DIR}/ANTIGRAVITY.md" "${USER_DIR}/AGENTS.md" "${USER_DIR}/CLAUDE.md" 2>/dev/null || true
echo

echo "=== User Settings (Antigravity keys) ==="
python3 - "${SETTINGS_PATH}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print(f"missing settings file: {path}")
    raise SystemExit(1)

settings = json.loads(path.read_text())
keys = [
    "kilo-code.useAgentRules",
    "kilo-code.allowedCommands",
    "kilo-code.deniedCommands",
    "roo-cline.useAgentRules",
    "roo-cline.allowedCommands",
    "roo-cline.deniedCommands",
    "claudeCode.useTerminal",
    "geminicodeassist.rules",
    "geminicodeassist.agentYoloMode",
]
for k in keys:
    print(f"{k} = {settings.get(k)!r}")
PY
echo

echo "=== Gemini Shell Wrapper Verification ==="
if [[ -x "${GEMINI_BASH}" ]]; then
  PATH="${ROOT_DIR}/.gemini/bin:${PATH}" GEMINI_YOLO_MODE=false bash -c 'hostname && python3 -c "import os, platform; print(platform.system()); print(os.getenv(\"IN_MODAL_TASK_RUNNER\"))"'
else
  echo "missing executable wrapper: ${GEMINI_BASH}"
fi
echo

echo "=== Modal Runner Verification ==="
"${RUNNER}" -c 'hostname && python3 -c "import os, platform; print(platform.system()); print(os.getenv(\"IN_MODAL_TASK_RUNNER\"))"'
