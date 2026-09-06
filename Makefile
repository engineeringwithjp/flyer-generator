VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: install fonts generate preview ingest validate test lint typecheck check clean

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[drive,dev]"
	$(PY) scripts/fetch_fonts.py || echo "font download skipped (offline) - bundled fallbacks will be used"

fonts:
	$(PY) scripts/fetch_fonts.py

generate:
	$(PY) -m app.cli generate

# End-to-end render with no Claude calls and no Drive upload
preview:
	FLYER_OFFLINE=1 $(PY) -m app.cli generate --no-upload

ingest:
	$(PY) -m app.cli ingest-reference references/inbox

validate:
	$(PY) -m app.cli validate

test:
	$(VENV)/bin/pytest -q -m "not integration"

lint:
	$(VENV)/bin/ruff check app tests scripts
	$(VENV)/bin/ruff format --check app tests scripts

typecheck:
	$(VENV)/bin/mypy app

check: lint test

clean:
	rm -rf output/* .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
