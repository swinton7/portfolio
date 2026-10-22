FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.135.0 uvicorn==0.40.0 "psycopg[binary]==3.2.9" requests==2.32.5 pyyaml==6.0.2
COPY *.py .
