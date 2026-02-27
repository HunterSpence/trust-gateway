# Multi-stage build for Trust Gateway
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application
COPY trust_gateway ./trust_gateway
COPY trust_gateway_sdk ./trust_gateway_sdk

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/trust_gateway.db
ENV SECRET_KEY=change-this-secret-key-in-production
ENV API_KEY=change-this-api-key-in-production

# Create data directory
RUN mkdir -p /data

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8002/health').raise_for_status()"

# Run application
CMD ["python", "-m", "uvicorn", "trust_gateway.main:app", "--host", "0.0.0.0", "--port", "8002"]
