FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first (build context is repo root)
COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install rag retrieval dependencies with CPU-only PyTorch from pre-built wheels
COPY apps/backend/rag-retrieval-requirements.txt /tmp/rag-retrieval-requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/rag-retrieval-requirements.txt

# Copy application source
COPY apps/backend/ .

# Copy mcp-servers as mcp_servers (underscore — required for Python import)
COPY mcp-servers/ ./mcp_servers/

# Rename hyphenated subdirectories to underscore so Python can import them
RUN mv ./mcp_servers/alarm-management ./mcp_servers/alarm_management 2>/dev/null || true

# Copy rag package
COPY rag/ ./rag/

# Add app root to Python path so mcp_servers and rag are importable
ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["python", "main.py"]
