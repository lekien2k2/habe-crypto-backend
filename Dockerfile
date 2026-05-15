# Dockerfile for HABE Crypto Backend
# Multi-stage build: compile charm-crypto, then run the app

FROM python:3.10-slim as builder

# Install system dependencies for charm-crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libgmp-dev \
    libpbc-dev \
    libssl-dev \
    flex \
    bison \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install PBC library from source (if not available via apt)
RUN apt-get update && apt-get install -y libpbc-dev || ( \
    wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz && \
    tar xzf pbc-0.5.14.tar.gz && \
    cd pbc-0.5.14 && \
    ./configure && make && make install && \
    ldconfig && cd .. && rm -rf pbc-0.5.14* \
    )

# Install charm-crypto from source
RUN git clone https://github.com/JHUISI/charm.git /tmp/charm && \
    cd /tmp/charm && \
    pip install --no-cache-dir setuptools && \
    ./configure.sh && \
    make && \
    make install && \
    ldconfig && \
    rm -rf /tmp/charm

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.10-slim

# Install runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgmp10 \
    libpbc1 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/lib/libpbc* /usr/local/lib/
COPY --from=builder /usr/local/lib/libcharm* /usr/local/lib/
RUN ldconfig

# Copy application code
WORKDIR /app
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); exit(0 if r.status_code == 200 else 1)" || exit 1

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
