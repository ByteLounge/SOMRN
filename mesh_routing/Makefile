.PHONY: test batch plots clean lint demo poster beginner compare

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

demo:
	python main.py --demo

poster:
	python experiments/generate_poster_graphic.py

beginner:
	python main.py --protocol cpqr --scenario earthquake \
	    --mode beginner --live

compare:
	python main.py --protocol cpqr --scenario campus \
	    --mode intermediate --compare --live
