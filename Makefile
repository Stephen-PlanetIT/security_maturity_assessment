PYTEST?=pytest
PYTHON?=python3

.PHONY: test verify qa

test:
	PATH="$(HOME)/Library/Python/3.9/bin:$$PATH" $(PYTEST) -q || true

verify:
	@if [ -x "venv/bin/python" ]; then \
		venv/bin/python tools/verification_script.py || true; \
	elif [ -x ".venv/bin/python" ]; then \
		.venv/bin/python tools/verification_script.py || true; \
	else \
		$(PYTHON) tools/verification_script.py || true; \
	fi

qa: test verify

# Python 3.12 virtualenv and run helpers
venv-3.12:
	python3.12 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -r requirements.txt

run:
	. .venv/bin/activate && streamlit run app.py

docker-build:
	docker build -t secusecase:latest .

docker-run:
	docker run --rm -p 8501:8501 secusecase:latest
