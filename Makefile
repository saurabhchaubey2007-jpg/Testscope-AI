.PHONY: install dev test db-up db-down

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt || ./venv/bin/pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy psycopg2-binary langchain langgraph langchain-google-genai langchain-groq pytest httpx python-dotenv pytest-asyncio

dev:
	./venv/bin/uvicorn apps.api.app.main:app --reload

test:
	./venv/bin/pytest

db-up:
	docker-compose up -d

db-down:
	docker-compose down
