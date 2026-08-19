FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt config.yaml ./
COPY src/ src/

RUN pip install --no-cache-dir -e ".[ml]"

# Generate mock data at build time so the app starts with data available
RUN python -m market_predictor.cli generate-data --mode mock

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "visualize.py", "--server.port=8501", "--server.address=0.0.0.0"]
