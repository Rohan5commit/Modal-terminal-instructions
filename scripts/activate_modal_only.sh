#!/bin/bash
set -euo pipefail

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  SCRIPT_PATH="${(%):-%x}"
else
  SCRIPT_PATH="$0"
fi
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && /bin/pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && /bin/pwd)"
SHIMS_DIR="${ROOT_DIR}/.modal-shims"

if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Run this as: source scripts/activate_modal_only.sh" >&2
  exit 1
fi

if [[ ! -d "$SHIMS_DIR" ]] || [[ -z "$(/usr/bin/find "$SHIMS_DIR" -mindepth 1 -maxdepth 1 -type f -print -quit 2>/dev/null)" ]]; then
  "${ROOT_DIR}/scripts/install_modal_shims.sh"
fi

path_clean="${PATH:-}"
path_clean=":${path_clean}:"
path_clean="${path_clean//:${SHIMS_DIR}:/:}"
path_clean="${path_clean#:}"
path_clean="${path_clean%:}"
export PATH="${SHIMS_DIR}${path_clean:+:${path_clean}}"
unset path_clean

export MODAL_SHIMS_ACTIVE=1
export MODAL_CPU="${MODAL_CPU:-6}"
export MODAL_MEMORY_MB="${MODAL_MEMORY_MB:-14336}"
export MODAL_RUN_FLAGS="${MODAL_RUN_FLAGS-}"
export MODAL_SYNC_BACK="${MODAL_SYNC_BACK:-1}"

if command -v rehash >/dev/null 2>&1; then
  rehash
fi

echo "Modal-only shims active: ${SHIMS_DIR}"
echo "Defaults: MODAL_CPU=${MODAL_CPU} MODAL_MEMORY_MB=${MODAL_MEMORY_MB} MODAL_RUN_FLAGS='${MODAL_RUN_FLAGS}'"
