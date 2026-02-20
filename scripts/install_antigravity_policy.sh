#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"

POLICY_SRC="${ROOT_DIR}/ANTIGRAVITY.md"
WORKSPACE_AGENTS="${ROOT_DIR}/AGENTS.md"
WORKSPACE_CLINE="${ROOT_DIR}/.clinerules"
WORKSPACE_VSCODE_SETTINGS="${ROOT_DIR}/.vscode/settings.json"
WORKSPACE_RULES_DIR="${ROOT_DIR}/.rules"
WORKSPACE_ANTIGRAVITY_RULE="${WORKSPACE_RULES_DIR}/antigravity.rules"
WORKSPACE_CODEX_RULE="${WORKSPACE_RULES_DIR}/codex.rules"
WORKSPACE_GEMINI_DIR="${ROOT_DIR}/.gemini"
WORKSPACE_GEMINI_BIN_DIR="${WORKSPACE_GEMINI_DIR}/bin"
WORKSPACE_GEMINI_BASH="${WORKSPACE_GEMINI_BIN_DIR}/bash"
WORKSPACE_GEMINI_ENV="${WORKSPACE_GEMINI_DIR}/.env"
WORKSPACE_GEMINI_ENV_BEGIN="# >>> modal-gemini-routing (untitled-folder) >>>"
WORKSPACE_GEMINI_ENV_END="# <<< modal-gemini-routing (untitled-folder) <<<"

USER_DIR="${HOME}/Library/Application Support/Antigravity/User"
USER_POLICY="${USER_DIR}/ANTIGRAVITY.md"
USER_AGENTS="${USER_DIR}/AGENTS.md"
USER_CLAUDE="${USER_DIR}/CLAUDE.md"
SETTINGS_PATH="${USER_DIR}/settings.json"
RUNNER_PATH="${HOME}/.local/bin/modal-agent-runner"
MODAL_EXEC_PATH="${ROOT_DIR}/scripts/modal_exec.sh"

strip_block() {
  local file="$1"
  local begin="$2"
  local end="$3"
  local tmp_file="$4"
  /usr/bin/awk -v begin="$begin" -v end="$end" '
    $0 == begin {skip=1; next}
    $0 == end {skip=0; next}
    !skip {print}
  ' "$file" > "$tmp_file"
}

upsert_block() {
  local file="$1"
  local begin="$2"
  local end="$3"
  local block="$4"

  /usr/bin/touch "$file"
  local tmp_file
  tmp_file="$(/usr/bin/mktemp)"
  strip_block "$file" "$begin" "$end" "$tmp_file"

  if [[ -s "$tmp_file" ]]; then
    /bin/echo >> "$tmp_file"
  fi
  /bin/cat >> "$tmp_file" <<BLOCK
$block
BLOCK

  /bin/mv "$tmp_file" "$file"
}

/bin/mkdir -p "${WORKSPACE_RULES_DIR}" "${ROOT_DIR}/.vscode"
/bin/mkdir -p "${WORKSPACE_GEMINI_BIN_DIR}"
/bin/cp "${POLICY_SRC}" "${WORKSPACE_AGENTS}"
/bin/cp "${POLICY_SRC}" "${WORKSPACE_CLINE}"

/bin/cat > "${WORKSPACE_ANTIGRAVITY_RULE}" <<'EOF'
Follow `ANTIGRAVITY.md` in the workspace root.

Applies to Codex, Gemini Code Assist, Cline, Kilo Code, Roo Code, and Claude Code.

Terminal commands must execute only via:

- `$HOME/.local/bin/modal-agent-runner -c "<command>"`
- `$HOME/.local/bin/modal-agent-runner -- <binary> <args...>`

Do not run direct local terminal commands when the action can be executed through Modal.
EOF

/bin/cat > "${WORKSPACE_CODEX_RULE}" <<'EOF'
Follow `ANTIGRAVITY.md` in the workspace root.

For all terminal commands, use only:

- `$HOME/.local/bin/modal-agent-runner -c "<command>"`
- `$HOME/.local/bin/modal-agent-runner -- <binary> <args...>`

Do not execute direct local commands when Modal routing is possible.
EOF

/bin/cat > "${WORKSPACE_GEMINI_BASH}" <<'EOF'
#!/bin/bash
set -euo pipefail

RUNNER="${HOME}/.local/bin/modal-agent-runner"
REAL_BASH="/bin/bash"

if [[ "$#" -eq 2 && "${1:-}" == "-c" && -x "$RUNNER" ]]; then
  exec "$RUNNER" -c "$2"
fi

if [[ -x "$REAL_BASH" ]]; then
  exec "$REAL_BASH" "$@"
fi

if command -v bash >/dev/null 2>&1; then
  exec "$(command -v bash)" "$@"
fi

echo "Error: unable to locate real bash executable." >&2
exit 127
EOF
/bin/chmod +x "${WORKSPACE_GEMINI_BASH}"

GEMINI_PATH_VALUE=".gemini/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
gemini_env_block="${WORKSPACE_GEMINI_ENV_BEGIN}
PATH=\"${GEMINI_PATH_VALUE}\"
GEMINI_YOLO_MODE=false
MODAL_CPU=6
MODAL_MEMORY_MB=14336
${WORKSPACE_GEMINI_ENV_END}"
upsert_block "${WORKSPACE_GEMINI_ENV}" "${WORKSPACE_GEMINI_ENV_BEGIN}" "${WORKSPACE_GEMINI_ENV_END}" "${gemini_env_block}"

python3 - "${WORKSPACE_VSCODE_SETTINGS}" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
if settings_path.exists():
    settings = json.loads(settings_path.read_text())
else:
    settings = {}

settings["geminicodeassist.rules"] = (
    'Follow ANTIGRAVITY.md in the workspace root. For terminal execution, '
    'only use $HOME/.local/bin/modal-agent-runner -c "<command>" or '
    '$HOME/.local/bin/modal-agent-runner -- <binary> <args...>. '
    "Do not run direct local terminal commands when Modal routing is possible."
)
settings["geminicodeassist.agentYoloMode"] = False

env_osx = settings.setdefault("terminal.integrated.env.osx", {})
env_osx["PATH"] = "${workspaceFolder}/.modal-shims:${env:PATH}"
env_osx["MODAL_CPU"] = "6"
env_osx["MODAL_MEMORY_MB"] = "14336"
env_osx["MODAL_RUN_FLAGS"] = ""
env_osx["MODAL_SYNC_BACK"] = "1"

settings_path.write_text(json.dumps(settings, indent=4) + "\n")
PY

if [[ "${IN_MODAL_TASK_RUNNER:-0}" == "1" ]]; then
  /bin/cat <<EOF
Installed workspace Antigravity unified policy files.

Workspace files:
  ${POLICY_SRC}
  ${WORKSPACE_AGENTS}
  ${WORKSPACE_CLINE}
  ${WORKSPACE_ANTIGRAVITY_RULE}
  ${WORKSPACE_CODEX_RULE}
  ${WORKSPACE_VSCODE_SETTINGS} (geminicodeassist.rules)
  ${WORKSPACE_GEMINI_BASH}
  ${WORKSPACE_GEMINI_ENV}

Skipped user-level installation because this script is running inside Modal.
To install user-level Antigravity files and settings on your Mac profile, run:
  ./scripts/install_antigravity_policy.sh
from a local shell (outside modal_exec.sh).
EOF
  exit 0
fi

"${ROOT_DIR}/scripts/install_agent_runner.sh"

/bin/mkdir -p "${USER_DIR}"
/bin/cp "${POLICY_SRC}" "${USER_POLICY}"
/bin/ln -sfn "${USER_POLICY}" "${USER_AGENTS}"
/bin/ln -sfn "${USER_POLICY}" "${USER_CLAUDE}"

python3 - "${SETTINGS_PATH}" "${RUNNER_PATH}" "${MODAL_EXEC_PATH}" <<'PY'
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
runner_path = sys.argv[2]
modal_exec_path = sys.argv[3]

if settings_path.exists():
    settings = json.loads(settings_path.read_text())
else:
    settings = {}

allowed = [
    runner_path,
    "modal-agent-runner",
    f"{runner_path} -c",
    f"{runner_path} --",
    modal_exec_path,
    "./scripts/modal_exec.sh",
    "python3 -m modal",
    "/usr/bin/python3 -m modal",
]

settings["kilo-code.useAgentRules"] = True
settings["roo-cline.useAgentRules"] = True
settings["claudeCode.useTerminal"] = True

settings["kilo-code.allowedCommands"] = allowed
settings["kilo-code.deniedCommands"] = ["*"]
settings["roo-cline.allowedCommands"] = allowed
settings["roo-cline.deniedCommands"] = ["*"]

settings["geminicodeassist.rules"] = (
    'Follow ANTIGRAVITY.md in the workspace root. For terminal execution, '
    'only use $HOME/.local/bin/modal-agent-runner -c "<command>" or '
    '$HOME/.local/bin/modal-agent-runner -- <binary> <args...>. '
    "Do not run direct local terminal commands when Modal routing is possible."
)
settings["geminicodeassist.agentYoloMode"] = False

settings_path.write_text(json.dumps(settings, indent=4) + "\n")
PY

/bin/cat <<EOF
Installed Antigravity unified policy.

Workspace files:
  ${POLICY_SRC}
  ${WORKSPACE_AGENTS}
  ${WORKSPACE_CLINE}
  ${WORKSPACE_ANTIGRAVITY_RULE}
  ${WORKSPACE_CODEX_RULE}
  ${WORKSPACE_VSCODE_SETTINGS}
  ${WORKSPACE_GEMINI_BASH}
  ${WORKSPACE_GEMINI_ENV}

User-level files:
  ${USER_POLICY}
  ${USER_AGENTS} -> ${USER_POLICY}
  ${USER_CLAUDE} -> ${USER_POLICY}

Updated settings:
  ${SETTINGS_PATH}
  - kilo-code.useAgentRules=true
  - roo-cline.useAgentRules=true
  - claudeCode.useTerminal=true
  - geminicodeassist.rules set
  - geminicodeassist.agentYoloMode=false
  - kilo/roo deniedCommands=['*'] with modal runner allowlist

Next:
  make antigravity-policy-check
EOF
