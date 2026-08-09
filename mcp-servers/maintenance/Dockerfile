FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY . .

# Create proper package structure
RUN mkdir -p mcp_servers/maintenance && mv server.py mcp_servers/maintenance/ && mv config.py mcp_servers/maintenance/ && touch mcp_servers/__init__.py && touch mcp_servers/maintenance/__init__.py

# Run as non-root user
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Streamable-HTTP transport listens on 9001
EXPOSE 9001

CMD ["python", "-m", "mcp_servers.maintenance.server"]
