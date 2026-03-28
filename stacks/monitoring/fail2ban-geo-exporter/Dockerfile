FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml .
RUN uv pip install --system --no-cache .

COPY exporter.py .

RUN mkdir -p /data/geoip

EXPOSE 9122

CMD ["python", "-u", "exporter.py"]
