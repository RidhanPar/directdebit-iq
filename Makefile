PYTHON ?= python
STREAMLIT ?= streamlit
MLFLOW ?= mlflow

.PHONY: install data sql train test app mlflow all

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
	mlflow ui --backend-store-uri sqlite:///mlflow.db

all: data sql train test
