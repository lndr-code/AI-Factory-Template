FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    bash \
    nodejs \
    npm \
    gosu \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code @openai/codex

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV CLAUDE_CODE_BUBBLEWRAP=1

# Create non-root user so Claude Code can run with --dangerously-skip-permissions
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --home /home/appuser --shell /bin/bash appuser

WORKDIR /workspace

# Copy entrypoint that fixes /workspace ownership at container start
# (Docker volume mounts on Windows reset ownership to root at runtime)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Stay as root so entrypoint can chown, then entrypoint drops to appuser
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
