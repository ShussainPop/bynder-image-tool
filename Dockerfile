FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY alembic.ini .

RUN mkdir -p /app/infographics /app/data

EXPOSE 8501

CMD ["sh", "-c", "alembic upgrade head && streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"]
