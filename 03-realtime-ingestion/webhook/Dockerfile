FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.135.0 uvicorn==0.40.0 redis==7.1.0
COPY app.py .
HEALTHCHECK --interval=3s --timeout=3s --retries=20 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
