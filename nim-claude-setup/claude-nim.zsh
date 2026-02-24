# >>> claude-nim bridge >>>
_nim_local_env_file="$HOME/.nim-claude-local.env"
if [[ -f "$_nim_local_env_file" ]]; then
  # shellcheck disable=SC1090
  source "$_nim_local_env_file"
fi
_nim_claude_port="${NIM_PROXY_PORT:-8091}"
_nim_claude_base_url="http://localhost:${_nim_claude_port}"
_nim_claude_settings_file="$HOME/.claude/settings.json"
_nim_primary_model="${NIM_PRIMARY_MODEL:-qwen/qwen3-coder-480b-a35b-instruct}"
_nim_secondary_model="${NIM_SECONDARY_MODEL:-qwen/qwen2.5-coder-32b-instruct}"
_nim_primary_fallback_model="${NIM_PRIMARY_FALLBACK_MODEL:-qwen/qwen2.5-coder-32b-instruct}"
_nim_primary_display_name="${NIM_PRIMARY_DISPLAY_NAME:-Qwen 3 Coder 480B (Default)}"
_nim_secondary_display_name="${NIM_SECONDARY_DISPLAY_NAME:-Qwen 2.5 Coder 32B (Secondary)}"
_nim_default_selector_file="$HOME/.nim-claude-default-model"
_nim_legacy_selector_file="$HOME/.claude/nim-default-model"
_nim_proxy_pid_file="/tmp/nim-claude-proxy-${_nim_claude_port}.pid"
_nim_proxy_log_file="/tmp/nim-claude-proxy-${_nim_claude_port}.log"

if [[ ! -f "$_nim_default_selector_file" && -f "$_nim_legacy_selector_file" ]]; then
  cp "$_nim_legacy_selector_file" "$_nim_default_selector_file" >/dev/null 2>&1 || true
fi

_nim_claude_read_key() {
  local settings_file="$1"
  python3 - "$settings_file" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path, 'r', encoding='utf-8'))
except Exception:
    print("")
    raise SystemExit(0)

env = data.get('env') if isinstance(data, dict) else {}
if isinstance(env, dict):
    key = env.get('NIM_API_KEY') or env.get('NVIDIA_API_KEY') or env.get('MISTRAL_API_KEY')
    if isinstance(key, str):
        print(key.strip())
        raise SystemExit(0)
print("")
PY
}

_nim_current_default_alias() {
  local selected="primary"
  if [[ -f "$_nim_default_selector_file" ]]; then
    selected="$(tr -d '[:space:]' < "$_nim_default_selector_file")"
  fi

  case "$selected" in
    secondary|backup)
      printf '%s' "qwen25-coder-32b-secondary"
      ;;
    *)
      printf '%s' "qwen3-coder-480b-primary"
      ;;
  esac
}

claude-model() {
  local mode="${1:-status}"
  local current_alias

  case "$mode" in
    primary)
      mkdir -p "$HOME/.claude" >/dev/null 2>&1 || true
      printf 'primary\n' > "$_nim_default_selector_file"
      echo "Default model set to PRIMARY: $_nim_primary_model"
      ;;
    secondary)
      mkdir -p "$HOME/.claude" >/dev/null 2>&1 || true
      printf 'secondary\n' > "$_nim_default_selector_file"
      echo "Default model set to SECONDARY: $_nim_secondary_model"
      ;;
    status)
      current_alias="$(_nim_current_default_alias)"
      echo "Current default alias: $current_alias"
      echo "Primary:   $_nim_primary_model"
      echo "Secondary: $_nim_secondary_model"
      ;;
    *)
      echo "Usage: claude-model {primary|secondary|status}" >&2
      return 2
      ;;
  esac
}

nim-model() {
  local mode="${1:-pick}"
  local choice

  case "$mode" in
    pick|select)
      echo "Select Qwen model:"
      echo "1) Primary   - $_nim_primary_model"
      echo "2) Secondary - $_nim_secondary_model"
      printf "Choice [1/2]: "
      read -r choice
      case "$choice" in
        1|primary|p|"")
          claude-model primary
          ;;
        2|secondary|s)
          claude-model secondary
          ;;
        *)
          echo "Invalid choice: $choice" >&2
          return 2
          ;;
      esac
      ;;
    primary|secondary|status)
      claude-model "$mode"
      ;;
    *)
      echo "Usage: nim-model {pick|primary|secondary|status}" >&2
      return 2
      ;;
  esac
}

qwen-model() { nim-model "$@"; }

claude-primary() { claude --primary "$@"; }
claude-secondary() { claude --secondary "$@"; }

claude() {
  local nim_key="${NIM_API_KEY:-}"
  local -a claude_args
  local -a filtered_args
  local default_alias
  local force_alias=""
  local expect_model_value=0
  local has_model=0
  local arg=""

  claude_args=("$@")
  filtered_args=()
  for arg in "${claude_args[@]}"; do
    if [[ "$expect_model_value" -eq 1 ]]; then
      filtered_args+=("$arg")
      expect_model_value=0
      continue
    fi

    case "$arg" in
      --primary)
        force_alias="qwen3-coder-480b-primary"
        ;;
      --secondary)
        force_alias="qwen25-coder-32b-secondary"
        ;;
      --model)
        has_model=1
        expect_model_value=1
        filtered_args+=("$arg")
        ;;
      --model=*)
        has_model=1
        filtered_args+=("$arg")
        ;;
      *)
        filtered_args+=("$arg")
        ;;
    esac
  done

  if [[ -n "$force_alias" ]]; then
    filtered_args=(--model "$force_alias" "${filtered_args[@]}")
  elif [[ "$has_model" -eq 0 ]]; then
    default_alias="$(_nim_current_default_alias)"
    filtered_args=(--model "$default_alias" "${filtered_args[@]}")
  fi

  if [[ -z "$nim_key" ]]; then
    nim_key="$(_nim_claude_read_key "$_nim_claude_settings_file")"
  fi

  if [[ -z "$nim_key" ]]; then
    echo "NIM API key not found. Set NIM_API_KEY or add NIM_API_KEY in ~/.claude/settings.json" >&2
    return 1
  fi

  NIM_API_KEY="$nim_key" \
  NIM_PROXY_PORT="$_nim_claude_port" \
  NIM_PROXY_PID_FILE="$_nim_proxy_pid_file" \
  NIM_PROXY_LOG_FILE="$_nim_proxy_log_file" \
  NIM_PRIMARY_MODEL="$_nim_primary_model" \
  NIM_SECONDARY_MODEL="$_nim_secondary_model" \
  NIM_PRIMARY_FALLBACK_MODEL="$_nim_primary_fallback_model" \
  NIM_PRIMARY_DISPLAY_NAME="$_nim_primary_display_name" \
  NIM_SECONDARY_DISPLAY_NAME="$_nim_secondary_display_name" \
  nim-claude-proxy start >/dev/null 2>&1 || true

  CLAUDE_CODE_API_BASE_URL="$_nim_claude_base_url" \
  ANTHROPIC_BASE_URL="$_nim_claude_base_url" \
  ANTHROPIC_API_KEY="dummy" \
  ANTHROPIC_AUTH_TOKEN="dummy" \
  NIM_API_KEY="$nim_key" \
  NIM_PROXY_PORT="$_nim_claude_port" \
  NIM_PROXY_PID_FILE="$_nim_proxy_pid_file" \
  NIM_PROXY_LOG_FILE="$_nim_proxy_log_file" \
  NIM_PRIMARY_MODEL="$_nim_primary_model" \
  NIM_SECONDARY_MODEL="$_nim_secondary_model" \
  NIM_PRIMARY_FALLBACK_MODEL="$_nim_primary_fallback_model" \
  NIM_PRIMARY_DISPLAY_NAME="$_nim_primary_display_name" \
  NIM_SECONDARY_DISPLAY_NAME="$_nim_secondary_display_name" \
  command "$HOME/.local/bin/claude" "${filtered_args[@]}"
}
# <<< claude-nim bridge <<<
