VENV=.venv
PYTHON=${VENV}/bin/python
PIP=${VENV}/bin/pip

.PHONY: venv install test run clean

venv:
	python3 -m venv ${VENV}

install: venv
	${PIP} install -r requirements.txt

run:
	${PYTHON} scripts/run.py

test:
	${PYTHON} -m pytest -q

clean:
	rm -rf ${VENV} .pytest_cache __pycache__ build dist
