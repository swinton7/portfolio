FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir requests==2.34.2 beautifulsoup4==4.15.0 boto3==1.43.0
COPY scrape.py .
CMD ["python", "scrape.py"]
