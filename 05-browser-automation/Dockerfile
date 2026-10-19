FROM mcr.microsoft.com/playwright/python:v1.58.0-noble
WORKDIR /app
RUN pip install --no-cache-dir playwright==1.58.0
COPY automate.py .
CMD ["python", "automate.py"]
