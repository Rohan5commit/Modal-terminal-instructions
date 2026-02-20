#!/bin/bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"
SHIMS_DIR="${ROOT_DIR}/.modal-shims"

# Keep only minimal control-plane and source-control commands local.
exclude_commands=(
  ''
  sudo
  su
  login
  modal
  git
  gh
  make
  ssh
  scp
  sftp
  rsync
  open
  code
)

force_include_commands=(
  bash
  sh
  zsh
  python
  python3
  pip
  pip3
  uv
  node
  npm
  npx
  pnpm
  yarn
  rg
  find
  sed
  awk
  cat
  ls
  cp
  mv
  rm
  mkdir
  touch
)

should_exclude() {
  local cmd="$1"
  [[ -z "$cmd" ]] && return 0
  [[ "$cmd" == .* ]] && return 0
  local ex=""
  for ex in "${exclude_commands[@]}"; do
    [[ "$cmd" == "$ex" ]] && return 0
  done
  return 1
}

/bin/mkdir -p "$SHIMS_DIR"
/usr/bin/find "$SHIMS_DIR" -mindepth 1 -type f -delete 2>/dev/null || true
/usr/bin/find "$SHIMS_DIR" -mindepth 1 -type l -delete 2>/dev/null || true

commands=()
while IFS= read -r path_dir; do
  [[ -d "$path_dir" ]] || continue
  while IFS= read -r -d '' file; do
    [[ -d "$file" ]] && continue
    [[ -x "$file" ]] || continue
    commands+=("${file##*/}")
  done < <(/usr/bin/find "$path_dir" -maxdepth 1 -mindepth 1 -print0 2>/dev/null)
done < <(printf '%s' "$PATH" | /usr/bin/tr ':' '\n')

while IFS= read -r cmd; do
  [[ -n "$cmd" ]] && commands+=("$cmd")
done < <(compgen -c 2>/dev/null || true)

if [[ ${#force_include_commands[@]} -gt 0 ]]; then
  commands+=("${force_include_commands[@]}")
fi

generated=0
while IFS= read -r cmd; do
  should_exclude "$cmd" && continue
  [[ -z "$cmd" ]] && continue

  /bin/cat > "${SHIMS_DIR}/${cmd}" <<'EOF'
#!/bin/bash
set -euo pipefail
SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"
CMD_NAME="${0##*/}"

if [[ ("$CMD_NAME" == "python" || "$CMD_NAME" == "python3") && "${1:-}" == "-m" && "${2:-}" == "modal" ]]; then
  for py in "/usr/bin/${CMD_NAME}" "/opt/homebrew/bin/${CMD_NAME}" "/usr/local/bin/${CMD_NAME}"; do
    if [[ -x "$py" ]]; then
      exec "$py" "$@"
    fi
  done
fi

exec "${ROOT_DIR}/scripts/modal_exec.sh" -- "${CMD_NAME}" "$@"
EOF
  /bin/chmod +x "${SHIMS_DIR}/${cmd}"
  generated=$((generated + 1))
done < <(printf '%s\n' "${commands[@]}" | LC_ALL=C /usr/bin/sort -u)

/bin/cat <<EOF
Created modal shims in: ${SHIMS_DIR}
Shim count: ${generated}

Activate for this shell:
  source "${ROOT_DIR}/scripts/activate_modal_only.sh"
EOF
