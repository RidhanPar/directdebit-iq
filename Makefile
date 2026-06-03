PYTHON ?= python
STREAMLIT ?= streamlit
MLFLOW ?= mlflow
IMAGE_NAME ?= directdebit-iq
COMPOSE ?= docker compose

.PHONY: install data sql train test app mlflow docker-build docker-run docker-compose all

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

data:
	$(PYTHON) data/generate_data.py

sql:
	$(PYTHON) src/sql_runner.py

train:
	$(PYTHON) src/train.py

test:
	pytest -q

app:
	$(STREAMLIT) run streamlit_app.py

mlflow:
	$(MLFLOW) ui --backend-store-uri sqlite:///mlflow.db

docker-build:
	docker build -t $(IMAGE_NAME) .

docker-run:
	docker run --rm -p 8501:8501 $(IMAGE_NAME)

docker-compose:
	$(COMPOSE) up --build

all: data sql train test
