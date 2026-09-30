FROM python:3.11-slim
WORKDIR /app
COPY ingestion/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY ingestion /app/ingestion
RUN useradd --create-home --uid 10001 hse
USER hse
CMD ["python", "-m", "ingestion.main"]
