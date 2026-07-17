.PHONY: install dev test lint format ui

install:
	python -m pip install -e '.[dev]'

dev:
	uvicorn semantic_search_middleware.api.main:app --reload

ui:
	streamlit run app.py

test:
	pytest

lint:
	ruff check .
	mypy src

format:
	ruff format .
	ruff check --fix .
