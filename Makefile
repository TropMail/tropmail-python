.PHONY: install test lint typecheck contract build clean

VENV := .venv
PY := $(VENV)/bin/python

$(VENV):
	python3 -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev]"

install: $(VENV)

test: $(VENV)
	$(PY) -m pytest -q

lint: $(VENV)
	$(PY) -m ruff check src tests examples

typecheck: $(VENV)
	$(PY) -m mypy
	$(PY) -m mypy examples

contract: $(VENV)
	$(PY) -m pytest -q tests/test_contract.py

build: $(VENV)
	$(PY) -m pip install --quiet build
	$(PY) -m build

clean:
	rm -rf $(VENV) dist build .pytest_cache .mypy_cache .ruff_cache
