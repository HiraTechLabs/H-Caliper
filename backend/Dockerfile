FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system hcaliper && useradd --system --gid hcaliper --home-dir /app hcaliper

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod 0755 /app/docker-entrypoint.sh \
    && mkdir -p /var/lib/hcaliper/workspaces \
    && chown -R hcaliper:hcaliper /app /var/lib/hcaliper

USER hcaliper
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]
