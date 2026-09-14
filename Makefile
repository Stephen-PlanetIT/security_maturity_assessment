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
