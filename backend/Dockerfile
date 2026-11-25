FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app PATH=/usr/local/bin:$PATH
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app ./app
RUN mkdir -p /data && useradd -m appuser && chown -R appuser /data /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
