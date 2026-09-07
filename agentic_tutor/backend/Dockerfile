FROM python:3.12-slim
WORKDIR /app

# claude-agent-sdk does not call the model directly: it shells out to the Claude CLI
# (@anthropic-ai/claude-code), a Node.js program. Install Node 20 + the CLI as root so
# every agent turn (MAPPER/TEACHER/JUDGE/DISTILLER) has the binary on PATH at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/* /root/.npm

COPY tutor_v2/requirements-server.txt /app/requirements-server.txt
RUN pip install --no-cache-dir -r requirements-server.txt
COPY tutor_v2 /app/tutor_v2
RUN useradd --create-home tutor && mkdir -p /data /codebases && chown tutor:tutor /data /codebases
USER tutor
ENV STATE_ROOT=/data HOST=0.0.0.0 PORT=8000 CODEBASE_ROOT=/codebases
EXPOSE 8000
CMD ["python", "-m", "tutor_v2"]
