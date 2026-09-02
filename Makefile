EXAMPLES := $(wildcard examples/*.py)

all: test lint mypy coverage docs build

test: pytest doctest examples

pytest: test.py
	if which pytest >/dev/null 2>&1; then pytest $<; else python3 $<; fi

doctest: pygtrie.py
	python3 -m doctest $<

examples: $(EXAMPLES)
	for ex in $(EXAMPLES); do python3 "$$ex" </dev/null || exit; done

lint: .pylintrc pygtrie.py test.py $(EXAMPLES)
	lint=$$(which pylint3 2>/dev/null || which pylint) && \
	"$$lint" --rcfile $^

mypy: pygtrie.py $(EXAMPLES)
	mypy --strict $^

coverage: test.py pygtrie.py
	cov=$$(which python3-coverage 2>/dev/null || which coverage) && \
	"$$cov" run --source=pygtrie $< && "$$cov" report -m

build:
	python3 -m build -swn

docs:
	python3 setup.py build_doc

.PHONY: all build coverage docs doctest examples lint mypy pytest test
