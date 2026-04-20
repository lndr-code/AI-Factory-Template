#!/bin/bash
# Entrypoint: fix /workspace ownership at container start, then exec as appuser.
# Docker volume mounts on Windows reset ownership to root at runtime;
# this script (run as root) corrects it before handing off.

set -e

# Fix ownership of workspace (may be root-owned after Docker bind mount)
chown -R appuser:appuser /workspace

# Ensure auth dirs exist and are owned by appuser (external volumes start empty;
# Windows Docker resets ownership to root on every start)
mkdir -p /home/appuser/.claude /home/appuser/.codex
chown appuser:appuser /home/appuser/.claude /home/appuser/.codex
chmod 700 /home/appuser/.claude /home/appuser/.codex

# Configure git identity and safe.directory for appuser
su -s /bin/bash appuser -c "
  git config --global user.name 'Orchestrator Bot'
  git config --global user.email 'bot@ai-factory.local'
  git config --global --add safe.directory /workspace
"

# Drop to appuser and exec the command (preserves signals, PID 1, etc.)
export HOME=/home/appuser
exec gosu appuser "$@"
