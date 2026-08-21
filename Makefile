.PHONY: test benchmark run

test:
	python -m pytest -q

benchmark:
	python scripts/benchmark_voice_state.py

run:
	uvicorn server.app.main:app --reload --port 8000
