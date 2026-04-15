#!/bin/bash
# Entrypoint: fix /workspace ownership at container start, then exec as appuser.
# Docker volume mounts on Windows reset ownership to root at runtime;
# this script (run as root) corrects it before handing off.

set -e

# Fix ownership of workspace (may be root-owned after Docker bind mount)
chown -R appuser:appuser /workspace

# Configure git identity and safe.directory for appuser
su -s /bin/bash appuser -c "
  git config --global user.name 'Orchestrator Bot'
  git config --global user.email 'bot@ai-factory.local'
  git config --global --add safe.directory /workspace
"

# Drop to appuser and exec the command (preserves signals, PID 1, etc.)
exec gosu appuser "$@"
