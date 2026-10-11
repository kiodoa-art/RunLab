ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.22
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-pip && python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir fitparse==1.2.0
COPY rootfs/app /app
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" RUNLAB_DATA=/data
CMD ["python3", "server.py"]
