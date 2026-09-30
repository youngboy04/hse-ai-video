FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY inference /app/inference
RUN useradd --create-home --uid 10001 hse
USER hse
EXPOSE 8001
CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
