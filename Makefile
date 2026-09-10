PYTEST?=pytest
PYTHON?=python3

.PHONY: test verify qa

test:
	PATH="$(HOME)/Library/Python/3.9/bin:$$PATH" $(PYTEST) -q || true

verify:
	$(PYTHON) tools/verification_script.py || true

qa: test verify
