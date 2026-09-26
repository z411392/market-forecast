#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_DIR="${1:-$REPO_ROOT}"
AGENTS_PATH="${TARGET_DIR}/.agents"

if [ -L "${AGENTS_PATH}" ]; then
  CURRENT_TARGET="$(readlink "${AGENTS_PATH}")"
  if [ "${CURRENT_TARGET}" = ".claude" ] || [ "${CURRENT_TARGET}" = ".claude/" ]; then
    echo "bootstrap-agents: .agents already correctly links to .claude"
    exit 0
  else
    echo "bootstrap-agents error: .agents is a symlink to unexpected target: '${CURRENT_TARGET}', not '.claude'; refusing to overwrite" >&2
    exit 1
  fi
elif [ -e "${AGENTS_PATH}" ]; then
  echo "bootstrap-agents error: .agents exists and is not a symlink; refusing to overwrite" >&2
  exit 1
else
  (cd "${TARGET_DIR}" && ln -s .claude .agents)
  echo "bootstrap-agents: created symlink .agents -> .claude"
fi
