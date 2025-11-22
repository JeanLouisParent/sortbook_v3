.PHONY: install test lint clean run

install:
	pip install -e .

test:
	python -m unittest discover tests

lint:
	pip install ruff
	ruff check .

clean:
	rm -rf build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +

run:
	python src/epub_metadata.py
