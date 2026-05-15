# Dockerfile for HABE Crypto Backend
# Single-stage build on Debian Bookworm (has stable package support)

FROM python:3.10-slim-bookworm AS builder

# Install system dependencies for charm-crypto + PBC from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libgmp-dev \
    libssl-dev \
    flex \
    bison \
    git \
    wget \
    m4 \
    && rm -rf /var/lib/apt/lists/*

# Build PBC library from source (not available in Bookworm repos)
RUN wget -q https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz && \
    tar xzf pbc-0.5.14.tar.gz && \
    cd pbc-0.5.14 && \
    ./configure && make -j$(nproc) && make install && \
    ldconfig && \
    cd .. && rm -rf pbc-0.5.14*

# Install charm-crypto from source
RUN git clone https://github.com/JHUISI/charm.git /tmp/charm && \
    cd /tmp/charm && \
    pip install --no-cache-dir setuptools && \
    ./configure.sh && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    rm -rf /tmp/charm

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.10-slim-bookworm

# Install runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgmp10 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy PBC shared library from builder
COPY --from=builder /usr/local/lib/libpbc* /usr/local/lib/

# Copy installed Python packages and executables from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Update linker cache
RUN ldconfig

# Copy application code
WORKDIR /app
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
