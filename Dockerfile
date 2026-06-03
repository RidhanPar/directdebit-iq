# DirectDebit IQ — Streamlit + ML analytics container
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

# Copy dependency file first to maximise Docker layer caching.
COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

# Copy the application source code.
COPY . .

# Generate synthetic data inside the image because raw data is ignored by Docker.
RUN python data/generate_data.py

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
