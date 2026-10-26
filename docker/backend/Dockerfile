# Note: Per docs/ENVIRONMENT.md, GPU inference runs on the host with CUDA torch.
# This container runs the API and web services; CUDA torch is not baked here.
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend:/app

COPY pyproject.toml /app/
COPY configs/ /app/configs/
COPY benchmark/ /app/benchmark/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
