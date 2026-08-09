FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create proper package structure
RUN mkdir -p mcp_servers/alarm_management && mv server.py mcp_servers/alarm_management/ && touch mcp_servers/__init__.py && touch mcp_servers/alarm_management/__init__.py

# Streamable-HTTP transport listens on 9000
EXPOSE 9000

CMD ["python", "-m", "mcp_servers.alarm_management.server"]
