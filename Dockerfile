FROM python:3.12-slim

LABEL maintainer="iceslim409@gmail.com"
LABEL description="ICECODE Super-Agent Network v2.0.0"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files first for layer caching
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/server/pyproject.toml packages/server/pyproject.toml

# Install core Python dependencies
RUN pip install --no-cache-dir \
    "openai>=1.30.0" \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.29.0" \
    "httpx>=0.27.0" \
    "loguru>=0.7.2" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "python-multipart>=0.0.9" \
    "websockets>=12.0" \
    "aiofiles>=23.0" \
    "numpy>=1.24.0" \
    "PyPDF2>=3.0.0" \
    "faiss-cpu>=1.8.0"

# Copy the rest of the project
COPY packages/ packages/
COPY tests/ tests/
COPY pytest.ini .
COPY .env.example .env.example

# Install ICECODE packages
RUN pip install --no-cache-dir -e packages/core 2>/dev/null || true
RUN pip install --no-cache-dir -e packages/server 2>/dev/null || true

# Create data directories
RUN mkdir -p /root/.icecode/data /root/.icecode/sessions \
             /root/.icecode/skills /root/.icecode/logs \
             /root/.icecode/data/knowledge /root/.icecode/data/knowledge/uploads

# Copy .env if not mounted
RUN cp .env.example .env 2>/dev/null || true

EXPOSE 13210

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:13210/health || exit 1

ENV PYTHONPATH=/app/packages/core:/app/packages/server
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "icecode_server.main:app", \
     "--host", "0.0.0.0", "--port", "13210", \
     "--app-dir", "packages/server"]
