# Stage 1: Build web frontend
FROM node:20-slim AS web-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web-builder /web/dist ./web_dist/

# Decrypt restaurant data at build time
ARG DATA_ENCRYPTION_KEY
RUN if [ -n "$DATA_ENCRYPTION_KEY" ] && \
      ( [ -f data_bundle.tar.gz.enc ] || ls data_bundle.tar.gz.enc.part_* >/dev/null 2>&1 ); then \
      bash scripts/decrypt_data.sh; \
    fi

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
