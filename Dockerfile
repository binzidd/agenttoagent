# ─────────────────────────────────────────────────────────────────────────────
# Austral Agent Stack – Docker image
# Compatible with AWS Bedrock AgentCore container requirements.
#
# Build:   docker build -t austral-agent-stack .
# Run:     docker run -p 8080:8080 --env-file backend/.env austral-agent-stack
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

# AgentCore listens on 8080 by default
EXPOSE 8080

# Non-root user (AgentCore security requirement)
RUN useradd -m -u 1000 agentuser

WORKDIR /app

# Install Python deps first (layer cache)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir bedrock-agentcore 2>/dev/null || true
# Note: bedrock-agentcore SDK is injected by AgentCore at runtime.
# The '|| true' prevents build failure in local environments.

# Copy application code
COPY backend/ .

# AgentCore injects secrets as env vars at runtime — never bake credentials here
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER agentuser

# AgentCore entry point
CMD ["python", "main.py"]
