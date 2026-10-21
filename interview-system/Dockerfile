# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl nodejs \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Test stage: `docker build --target test .` fails the build on lint/test errors ----
FROM base AS test
ENV LLM_MODE=mock DATABASE_URL=sqlite:///./test.db
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
RUN flake8 && pytest -q

# ---- Runtime stage ----
FROM base AS runtime
RUN curl -fsSL -o /etc/ssl/certs/rds-global-bundle.pem \
      https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
    && useradd -r -u 1001 appuser \
    && mkdir -p /run/runner && chmod 777 /run/runner
COPY app ./app
USER appuser
ENV DB_SSL_CA=/etc/ssl/certs/rds-global-bundle.pem
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fs http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
