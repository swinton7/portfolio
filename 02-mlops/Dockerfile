FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir mlflow==3.16.1 psycopg2-binary==2.9.13 boto3==1.43.0 scikit-learn==1.9.1 pandas==3.0.6
COPY train.py .
