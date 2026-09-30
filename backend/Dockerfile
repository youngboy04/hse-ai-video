FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend /app/backend
COPY docs/evidence /app/docs/evidence
RUN useradd --create-home --uid 10001 hse && mkdir -p /data/snapshots && chown -R hse:hse /data /app
USER hse
ENV MEDIA_DIR=/data/snapshots
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
