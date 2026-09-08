FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends --yes iputils-ping net-tools \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system netwatch \
    && adduser --system --ingroup netwatch netwatch \
    && mkdir -p /app/data \
    && chown -R netwatch:netwatch /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=netwatch:netwatch backend/ ./
COPY --chown=netwatch:netwatch docker/backend-entrypoint.sh /usr/local/bin/netwatch-entrypoint
RUN chmod +x /usr/local/bin/netwatch-entrypoint

USER netwatch
EXPOSE 8000
ENTRYPOINT ["netwatch-entrypoint"]
