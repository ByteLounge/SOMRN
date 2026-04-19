.PHONY: run test batch plots clean lint

run:
	python main.py --protocol cpqr --live

test:
	pytest tests/ -v --cov=. --cov-report=term-missing

batch:
	python experiments/run_batch.py

plots:
	python experiments/plot_results.py

clean:
	rm -rf results/*.csv results/*.pdf results/*.png __pycache__ .pytest_cache

lint:
	black . && mypy .
