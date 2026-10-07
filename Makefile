.PHONY: install dev test db-up db-down web playwright

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

dev:
	./venv/bin/uvicorn apps.api.app.main:app --reload

test:
	./venv/bin/pytest

db-up:
	docker compose up -d

db-down:
	docker compose down

web:
	cd apps/web && npm run dev

playwright:
	./venv/bin/python -m playwright install chromium
