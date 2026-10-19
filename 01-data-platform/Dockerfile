FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir duckdb==1.5.6 dbt-core==1.12.6 dbt-duckdb==1.11.0 boto3==1.43.0 \
 && python -c "import duckdb; duckdb.connect().install_extension('httpfs')"
COPY generate.py run.sh ./
COPY dbt ./dbt
ENV DBT_PROFILES_DIR=/app/dbt
CMD ["sh", "run.sh"]
