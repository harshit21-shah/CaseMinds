.PHONY: install lint typecheck test seed run ui migrate eval-citations eval-overruled eval-all clean

install:
	poetry install

lint:
	ruff check services/ tests/
	black --check services/ tests/

lint-fix:
	ruff check --fix services/ tests/
	black services/ tests/

typecheck:
	mypy --strict services/

test:
	pytest tests/unit tests/integration -v

seed:
	python scripts/seed.py

migrate:
	alembic upgrade head

run:
	uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8080

ui:
	streamlit run services/ui/app.py --server.port 8501

frontend:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

eval-citations:
	pytest tests/eval/test_citation_accuracy.py -v

eval-overruled:
	pytest tests/eval/test_overruled_detection.py -v

eval-adversarial:
	pytest tests/eval/test_adversarial.py -v

eval-all: eval-citations eval-overruled eval-adversarial

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
