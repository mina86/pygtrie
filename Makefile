all: test lint mypy coverage docs build

test: pytest doctest

pytest: test.py
	if which pytest >/dev/null 2>&1; then pytest $<; else python3 $<; fi

doctest: pygtrie.py
	python3 -m doctest $<

lint: .pylintrc pygtrie.py test.py example.py
	lint=$$(which pylint3 2>/dev/null) || lint=$$(which pylint) && \
	"$$lint" --rcfile $^

mypy: pygtrie.py example.py
	mypy --strict $^

coverage: test.py pygtrie.py
	python3-coverage run --source=pygtrie $< && \
		python3-coverage report -m

build:
	python3 -m build -swn

docs:
	python3 setup.py build_doc

.PHONY: all build coverage docs doctest lint mypy pytest test
